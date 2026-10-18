"""Evidence admission and claim-level gates. Never promote generated text to evidence."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, List, Mapping, Sequence, Tuple
from urllib.parse import urlparse

from .models import ClaimRecord, EvidenceRecord, ProvenanceBundle, SourceRecord
from .normalizer import stable_id
from .relevance import (
    flatten_text,
    is_claim_text_supported,
    is_textually_related,
    meaningful_tokens,
)


FACT_TYPES = {"fact", "metric"}
FORECAST_TYPES = {"prediction", "recommendation"}
VALID_STATUSES = {"supported", "weak", "unsupported", "predicted"}
_RAW_TYPES = {
    "web",
    "social",
    "news",
    "text",
    "search_result",
    "ocr",
    "video",
    "comment",
    "multimodal",
    "image_metadata",
    "db_row",
    "db_agg",
}
_LOCATOR_ONLY_TYPES = {"image_metadata"}
_NUMBER_PATTERN = r"(?<![A-Za-z0-9])([+-]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+))"
_UNIT_PATTERN = (
    r"个百分点|percentage\s+points?|percent|%|％|"
    r"亿元|万元|千元|亿美元|万美元|美元|人民币|元|"
    r"亿人|万人|人|名|位|亿个|万个|个|亿次|万次|次|"
    r"万条|条|万家|家|件|份|起|例|辆|吨|公斤|千克|克|"
    r"公里|平方米|平方公里|米|小时|分钟|秒|天|日|周|月|年|岁|"
    r"rmb|cny|usd|yuan|dollars?|people|persons?|employees?|items?|times?|days?|years?"
)


def is_valid_evidence(record: EvidenceRecord, source: SourceRecord | None = None) -> bool:
    if not source or not record.evidence_id or not record.snippet.strip():
        return False
    if source.source_id != record.source_id:
        return False
    if "forum" in record.agent.lower() or "forum" in source.agent.lower():
        return False
    evidence_type = record.evidence_type.lower()
    if evidence_type not in _RAW_TYPES or source.source_type.lower() not in _RAW_TYPES | {"database"}:
        return False
    if evidence_type in {"db_row", "db_agg"} or record.agent == "insight_engine":
        if evidence_type not in {"db_row", "db_agg"}:
            return False
        scope = record.scope
        required = {"query_time", "table", "filters", "time_window", "sample_size", "aggregation_method", "row_ids"}
        if not required.issubset(scope):
            return False
        if not all(scope.get(key) for key in ("query_time", "table", "time_window", "aggregation_method", "row_ids")):
            return False
        if not isinstance(scope["filters"], Mapping) or not isinstance(scope["time_window"], Mapping):
            return False
        if not isinstance(scope["row_ids"], list) or any(item in (None, "") for item in scope["row_ids"]):
            return False
        try:
            if int(scope["sample_size"]) <= 0:
                return False
        except (TypeError, ValueError, OverflowError):
            return False
        if evidence_type == "db_row" and scope.get("primary_key", scope.get("record_id")) in (None, ""):
            return False
        if evidence_type == "db_agg" and not scope.get("metric"):
            return False
        return True
    try:
        parsed = urlparse(source.url)
        has_url = parsed.scheme.lower() in {"https", "http"} and bool(parsed.netloc)
    except ValueError:
        has_url = False
    # A locator alone must identify a platform record, not an arbitrary label.
    has_record = bool(source.platform and (source.locator.get("post_id") or source.locator.get("comment_id")))
    return bool(has_url or has_record)


def filter_valid_evidence(bundle: ProvenanceBundle) -> ProvenanceBundle:
    result = copy.deepcopy(bundle)
    source_index = {item.source_id: item for item in result.sources}
    result.evidence = [item for item in result.evidence if is_valid_evidence(item, source_index.get(item.source_id))]
    source_ids = {item.source_id for item in result.evidence}
    result.sources = [item for item in result.sources if item.source_id in source_ids]
    result.claims, _ = gate_claims(result.claims, result)
    return result


@dataclass
class ClaimGateResult:
    claim: ClaimRecord
    allowed: bool
    reason: str = ""


def _numbers(text: str) -> set[Decimal]:
    values: set[Decimal] = set()
    for match in re.findall(_NUMBER_PATTERN, str(text or "")):
        try:
            values.add(Decimal(match.replace(",", "")))
        except InvalidOperation:
            continue
    return values


def _normalize_unit(unit: str) -> str:
    normalized = re.sub(r"\s+", " ", str(unit or "").strip().lower())
    aliases = {
        "％": "%",
        "percent": "%",
        "percentage point": "个百分点",
        "percentage points": "个百分点",
        "rmb": "元",
        "cny": "元",
        "yuan": "元",
        "person": "人",
        "persons": "人",
        "people": "人",
        "employee": "人",
        "employees": "人",
        "item": "个",
        "items": "个",
        "time": "次",
        "times": "次",
        "day": "天",
        "days": "天",
        "year": "年",
        "years": "年",
    }
    return aliases.get(normalized, normalized)


def _number_mentions(text: str) -> list[tuple[Decimal, str]]:
    pattern = re.compile(
        rf"{_NUMBER_PATTERN}\s*(?P<unit>{_UNIT_PATTERN})?",
        flags=re.IGNORECASE,
    )
    mentions: list[tuple[Decimal, str]] = []
    for match in pattern.finditer(str(text or "")):
        try:
            number = Decimal(match.group(1).replace(",", ""))
        except InvalidOperation:
            continue
        mentions.append((number, _normalize_unit(match.group("unit") or "")))
    return mentions


def _numbers_and_units_are_supported(claim_text: str, support_text: str) -> bool:
    """Reject equal digits carrying a conflicting explicit measurement unit."""
    if not _numbers(claim_text).issubset(_numbers(support_text)):
        return False
    support_mentions = _number_mentions(support_text)
    for claim_number, claim_unit in _number_mentions(claim_text):
        if not claim_unit:
            continue
        matching_units = {
            unit for number, unit in support_mentions if number == claim_number and unit
        }
        if claim_unit not in matching_units:
            return False
    return True


def _evidence_support_text(record: EvidenceRecord) -> str:
    """Use only source-derived fields when checking whether evidence is related."""
    return " ".join(
        (
            record.snippet,
            flatten_text(record.normalized_value),
        )
    )


def gate_claim(claim: ClaimRecord | Mapping[str, Any], available_evidence_ids: Iterable[str] | ProvenanceBundle) -> ClaimGateResult:
    record = copy.deepcopy(claim) if isinstance(claim, ClaimRecord) else ClaimRecord.from_dict(claim)
    bundle = available_evidence_ids if isinstance(available_evidence_ids, ProvenanceBundle) else None
    evidence_index = {item.evidence_id: item for item in bundle.evidence} if bundle else {}
    available = set(evidence_index) if bundle else set(available_evidence_ids)
    aliases = bundle.meta.get("evidence_aliases", {}) if bundle else {}
    refs = [aliases.get(item, item) for item in record.evidence_ids]
    record.evidence_ids = list(dict.fromkeys(item for item in refs if item in available))
    record.claim_type = (record.claim_type or "fact").lower()
    if not record.text.strip():
        return ClaimGateResult(record, False, "claim 缺少正文")
    if not record.claim_id:
        record.claim_id = stable_id("claim", record.claim_type, record.text, record.evidence_ids)
    if bundle and record.evidence_ids:
        # Image metadata identifies an artifact but does not contain readable
        # source content.  Keep it in the audit bundle for navigation while
        # preventing it from supporting any generated claim.
        record.evidence_ids = [
            item
            for item in record.evidence_ids
            if evidence_index[item].evidence_type.lower() not in _LOCATOR_ONLY_TYPES
        ]
        # An existing ID and a matching number are insufficient: the evidence
        # must also share a meaningful subject token with the claim.  This
        # prevents, for example, an employee-count source from supporting a
        # sales-count claim merely because both contain the number 100.
        if record.claim_type in FACT_TYPES:
            record.evidence_ids = [
                item
                for item in record.evidence_ids
                if is_claim_text_supported(
                    record.text,
                    _evidence_support_text(evidence_index[item]),
                )
                and _numbers_and_units_are_supported(
                    record.text,
                    _evidence_support_text(evidence_index[item]),
                )
            ]
        else:
            record.evidence_ids = [
                item
                for item in record.evidence_ids
                if is_textually_related(
                    record.text,
                    _evidence_support_text(evidence_index[item]),
                )
            ]
        evidence = [evidence_index[item] for item in record.evidence_ids]
        for key in ("subject", "time_range", "platform", "condition"):
            values = [item.scope.get(key) for item in evidence if item.scope.get(key)]
            if values and all(value == values[0] for value in values):
                record.scope.setdefault(key, copy.deepcopy(values[0]))
        existing_reasons = record.meta.get("evidence_selection_reasons") or {}
        reasons = {}
        for evidence_id in record.evidence_ids:
            reason = (
                existing_reasons.get(evidence_id)
                if isinstance(existing_reasons, Mapping)
                else ""
            )
            if not reason:
                reason = evidence_index[evidence_id].meta.get("selection_reason")
            if reason:
                reasons[evidence_id] = str(reason)
        if reasons:
            record.meta["evidence_selection_reasons"] = reasons
        else:
            record.meta.pop("evidence_selection_reasons", None)

    if record.claim_type in FACT_TYPES:
        allowed = bool(record.evidence_ids)
        record.status = record.support_level = "supported" if allowed else "unsupported"
        return ClaimGateResult(record, allowed, "事实或指标必须绑定有效证据，数字必须出现在证据中")
    if record.claim_type == "inference":
        count = len(record.evidence_ids)
        record.status = record.support_level = "supported" if count >= 2 else "weak" if count else "unsupported"
        return ClaimGateResult(
            record,
            count >= 2,
            "推断至少需要两条有效证据；不足时不得进入报告",
        )
    if record.claim_type in FORECAST_TYPES:
        record.status = record.support_level = "predicted"
        record.meta["display_label"] = "预测" if record.claim_type == "prediction" else "建议"
        return ClaimGateResult(record, True, "预测或建议必须单独显示")
    record.status = record.support_level = "unsupported"
    return ClaimGateResult(record, False, "未知 claim 类型")


def gate_claims(claims: Sequence[ClaimRecord | Mapping[str, Any]] | None, available_evidence_ids: Iterable[str] | ProvenanceBundle) -> Tuple[List[ClaimRecord], List[ClaimGateResult]]:
    accepted, rejected = [], []
    available = available_evidence_ids if isinstance(available_evidence_ids, ProvenanceBundle) else set(available_evidence_ids)
    for claim in claims or []:
        if not isinstance(claim, (ClaimRecord, Mapping)):
            continue
        result = gate_claim(claim, available)
        (accepted if result.allowed else rejected).append(result.claim if result.allowed else result)
    return accepted, rejected


def _claim_paragraph(claims: List[ClaimRecord]) -> dict:
    cursor, parts = 0, []
    for claim in claims:
        if parts:
            cursor += 1
        claim.text_span = {"start": cursor, "end": cursor + len(claim.text)}
        cursor += len(claim.text)
        parts.append(claim.text)
    statuses = {item.status for item in claims}
    return {
        "type": "paragraph",
        "inlines": [{"text": " ".join(parts)}],
        "claims": [item.to_dict() for item in claims],
        "citation_refs": list(dict.fromkeys(ref for item in claims for ref in item.evidence_ids)),
        "support_status": "predicted" if "predicted" in statuses else "weak" if "weak" in statuses else "supported",
    }


def sanitize_claim_block(block: Mapping[str, Any], available_evidence_ids: Iterable[str] | ProvenanceBundle) -> dict:
    """Rebuild from allowed claims so unclaimed text cannot hitchhike on a citation."""
    accepted, _ = gate_claims(block.get("claims"), available_evidence_ids)
    return _claim_paragraph(accepted) if accepted else {}


def _claim_groups(claims: Sequence[ClaimRecord]) -> list[list[ClaimRecord]]:
    groups: dict[str, list[ClaimRecord]] = {}
    for claim in claims:
        group = claim.claim_type if claim.claim_type in FORECAST_TYPES else claim.status
        groups.setdefault(group, []).append(claim)
    return list(groups.values())


def _apply_block_provenance(block: dict, claims: Sequence[ClaimRecord]) -> None:
    """Replace model supplied provenance fields with the admitted claim set."""
    block["claims"] = [item.to_dict() for item in claims]
    block["citation_refs"] = list(
        dict.fromkeys(ref for item in claims for ref in item.evidence_ids)
    )
    statuses = {item.status for item in claims}
    block["support_status"] = (
        "predicted"
        if "predicted" in statuses
        else "weak"
        if "weak" in statuses
        else "supported"
    )


def _inline_text(block: Mapping[str, Any]) -> str:
    return " ".join(
        str(item.get("text") or "")
        for item in block.get("inlines", []) or []
        if isinstance(item, Mapping)
    ).strip()


def _claims_cover_text(text: str, claims: Sequence[ClaimRecord]) -> bool:
    """Require inherited parent claims to cover each child payload separately."""
    if not text.strip() or not claims:
        return False
    claim_text = " ".join(item.text for item in claims)
    if not _numbers_and_units_are_supported(text, claim_text):
        return False
    if meaningful_tokens(text):
        return is_claim_text_supported(text, claim_text)
    if _numbers(text):
        return True
    # A separately stored KPI unit is visible too.  It must be a measurement
    # unit explicitly attached to an admitted number, not arbitrary symbols.
    return bool(re.fullmatch(_UNIT_PATTERN, text.strip(), flags=re.IGNORECASE)) and (
        _normalize_unit(text) in {unit for _, unit in _number_mentions(claim_text)}
    )


def _leaf_payload_fields(block: Mapping[str, Any]) -> dict:
    """Extract user-visible leaf data while excluding IR/provenance plumbing."""
    ignored = {
        "type",
        "claims",
        "citation_refs",
        "support_status",
        "style",
        "widgetId",
        "widgetType",
        "anchor",
        "id",
        "level",
        "lang",
        "cols",
        "displayMode",
        "responsive",
    }
    return {key: value for key, value in block.items() if key not in ignored}


def _payload_parts(value: Any) -> list[str]:
    """Check every displayed value; one correct value cannot shelter another."""
    if isinstance(value, Mapping):
        parts = []
        for key, item in value.items():
            # These are presentation enums, not displayed prose or data.
            if key in {"deltaTone", "style"}:
                continue
            if key == "unit" and "value" in value:
                continue
            if key == "value" and value.get("unit"):
                item = f"{item}{value['unit']}"
            parts.extend(_payload_parts(item))
        return parts
    if isinstance(value, (list, tuple, set)):
        return [part for item in value for part in _payload_parts(item)]
    if value is None or isinstance(value, bool):
        return []
    text = str(value).strip()
    return [text] if text else []


def _claims_cover_leaf(block: Mapping[str, Any], claims: Sequence[ClaimRecord]) -> bool:
    parts = _payload_parts(_leaf_payload_fields(block))
    return bool(parts) and all(_claims_cover_text(part, claims) for part in parts)


def _sanitize_container_labels(block: dict, claims: Sequence[ClaimRecord]) -> None:
    """Containers retain supported children without laundering a new headline."""
    for field in ("title", "subtitle", "caption", "summary"):
        value = block.get(field)
        if value and not _claims_cover_text(str(value), claims):
            block.pop(field, None)


def _sanitize_block(
    block: Mapping[str, Any],
    evidence: Iterable[str] | ProvenanceBundle,
    *,
    inherited_claims: Sequence[ClaimRecord] = (),
    trusted_headings: Iterable[str] = (),
) -> list[dict]:
    """Sanitize one block without flattening its renderable IR structure."""
    original = copy.deepcopy(dict(block))
    kind = original.get("type")
    raw_claims = original.get("claims") or []
    claim_values = raw_claims if isinstance(raw_claims, list) else [raw_claims]
    valid_claim_values = [item for item in claim_values if isinstance(item, Mapping)]
    accepted, rejected = gate_claims(valid_claim_values, evidence)
    has_claims = bool(claim_values)
    if not has_claims:
        # An inherited payload can be covered by a parent's admitted claims,
        # but it cannot invent a second citation or overwrite their status.
        original.pop("claims", None)
        original.pop("citation_refs", None)
        original.pop("support_status", None)

    if kind == "paragraph":
        if has_claims:
            # Paragraph text is rebuilt from admitted claims so unsupported
            # prose cannot borrow a neighbouring citation.
            return [_claim_paragraph(group) for group in _claim_groups(accepted)]
        return [original] if _claims_cover_text(_inline_text(original), inherited_claims) else []

    if kind in {"hr", "pageBreak", "toc"} and not has_claims:
        return [original]

    if kind == "heading" and not has_claims and original.get("text") in trusted_headings:
        # Rebuild rather than copying, so a trusted title cannot shelter an
        # unclaimed subtitle, inlines, metadata, or provenance supplied by LLM.
        return [{key: original[key] for key in ("type", "level", "text", "anchor") if key in original}]

    # Rich blocks cannot safely be split claim by claim without knowing which
    # data point/cell each claim describes.  Preserve them only when every
    # supplied claim is admissible; otherwise discard the complete block.
    if has_claims and (rejected or len(accepted) != len(claim_values)):
        return []

    effective_claims = accepted or list(inherited_claims)
    if accepted:
        _apply_block_provenance(original, accepted)

    if kind == "heading":
        # Trusted chapter headings are supplied by the composer.  Generated
        # headings have the same evidence boundary as generated body text.
        return [original] if _claims_cover_leaf(original, effective_claims) else []

    if kind in {"blockquote", "engineQuote", "callout"}:
        _sanitize_container_labels(original, effective_claims)
        nested = sanitize_blocks(
            original.get("blocks"), evidence, _inherited_claims=effective_claims,
            trusted_headings=trusted_headings,
        )
        if not nested:
            return []
        original["blocks"] = nested
        return [original]

    if kind == "list":
        items = []
        for item in original.get("items", []) or []:
            nested = sanitize_blocks(
                item, evidence, _inherited_claims=effective_claims,
                trusted_headings=trusted_headings,
            )
            if nested:
                items.append(nested)
        if not items:
            return []
        original["items"] = items
        return [original]

    if kind == "table":
        _sanitize_container_labels(original, effective_claims)
        rows = []
        for row in original.get("rows", []) or []:
            if not isinstance(row, Mapping):
                return []
            cleaned_row = copy.deepcopy(dict(row))
            cells = []
            for cell in row.get("cells", []) or []:
                if not isinstance(cell, Mapping):
                    return []
                cleaned_cell = copy.deepcopy(dict(cell))
                nested = sanitize_blocks(
                    cell.get("blocks"), evidence, _inherited_claims=effective_claims,
                    trusted_headings=trusted_headings,
                )
                # Removing a cell changes the meaning and alignment of the
                # remaining table, so an unsupported cell rejects the table.
                if not nested:
                    return []
                cleaned_cell["blocks"] = nested
                cells.append(cleaned_cell)
            if not cells:
                return []
            cleaned_row["cells"] = cells
            rows.append(cleaned_row)
        if not rows:
            return []
        original["rows"] = rows
        return [original]

    # Leaf rich blocks (widget, KPI, SWOT/PEST, figure, code, math, …) keep
    # their native payload only when their own or their parent's claims cover
    # that payload.  This is deliberately conservative for scalar data that
    # cannot be sanitized recursively.
    return [original] if _claims_cover_leaf(original, effective_claims) else []


def sanitize_blocks(
    blocks: Any,
    evidence: Iterable[str] | ProvenanceBundle,
    *,
    _inherited_claims: Sequence[ClaimRecord] = (),
    trusted_headings: Iterable[str] = (),
) -> list[dict]:
    """Gate nested claims while preserving list/table/widget IR containers.

    Parent claims are passed down only as candidates.  Every child payload must
    independently match those claims, so one supported item cannot lend its
    citation to an unrelated sibling.
    """
    if not isinstance(blocks, list):
        return []
    heading_allowlist = frozenset(str(item) for item in trusted_headings)
    result: list[dict] = []
    for block in blocks:
        if isinstance(block, Mapping):
            result.extend(
                _sanitize_block(
                    block, evidence, inherited_claims=_inherited_claims,
                    trusted_headings=heading_allowlist,
                )
            )
    return result
