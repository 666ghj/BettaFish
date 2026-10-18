"""Resolve claim/evidence references into renderer-friendly citation details."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping

from .models import EvidenceRecord, ProvenanceBundle, SourceRecord


class CitationService:
    def __init__(self, provenance: ProvenanceBundle | Mapping[str, Any] | None = None):
        self.bundle = provenance if isinstance(provenance, ProvenanceBundle) else ProvenanceBundle.from_dict(provenance)
        self.sources: Dict[str, SourceRecord] = {item.source_id: item for item in self.bundle.sources}
        self.evidence: Dict[str, EvidenceRecord] = {item.evidence_id: item for item in self.bundle.evidence}
        self._numbers: Dict[str, int] = {}

    def evidence_ids_for_block(self, block: Mapping[str, Any]) -> List[str]:
        ids: List[str] = []
        ids.extend(str(item) for item in block.get("citation_refs", []) if item)
        for claim in block.get("claims", []) or []:
            if not isinstance(claim, Mapping):
                continue
            if claim.get("support_status") == "unsupported" or claim.get("status") == "unsupported":
                continue
            ids.extend(str(item) for item in claim.get("evidence_ids", []) if item)
        return list(dict.fromkeys(item for item in ids if item in self.evidence))

    def number_for(self, evidence_id: str) -> int:
        if evidence_id not in self._numbers:
            self._numbers[evidence_id] = len(self._numbers) + 1
        return self._numbers[evidence_id]

    def details_for_ids(
        self,
        evidence_ids: Iterable[str],
        selection_reasons: Mapping[str, str] | None = None,
    ) -> List[Dict[str, Any]]:
        details = []
        selection_reasons = selection_reasons or {}
        for evidence_id in evidence_ids:
            evidence = self.evidence.get(str(evidence_id))
            if evidence is None:
                continue
            source = self.sources.get(evidence.source_id, SourceRecord(source_id=evidence.source_id))
            details.append(
                {
                    "number": self.number_for(evidence.evidence_id),
                    "evidence_id": evidence.evidence_id,
                    "source_id": evidence.source_id,
                    "title": source.title or source.platform or evidence.evidence_id,
                    "url": source.url,
                    "platform": source.platform or source.meta.get("domain", ""),
                    "author": source.author,
                    "publish_time": source.publish_time,
                    "retrieved_time": source.retrieved_time,
                    "locator": source.locator,
                    "evidence_type": evidence.evidence_type,
                    "snippet": evidence.snippet,
                    "scope": evidence.scope,
                    "selection_reason": selection_reasons.get(evidence.evidence_id)
                    or evidence.meta.get("selection_reason", ""),
                }
            )
        return details

    def details_for_block(self, block: Mapping[str, Any]) -> List[Dict[str, Any]]:
        """Resolve citations with the chapter-scoped reason stored on each claim."""
        evidence_ids = self.evidence_ids_for_block(block)
        reasons: Dict[str, str] = {}
        for claim in block.get("claims", []) or []:
            if not isinstance(claim, Mapping):
                continue
            claim_reasons = (claim.get("meta") or {}).get(
                "evidence_selection_reasons"
            )
            if not isinstance(claim_reasons, Mapping):
                continue
            for evidence_id, reason in claim_reasons.items():
                if evidence_id in evidence_ids and reason:
                    reasons.setdefault(str(evidence_id), str(reason))
        return self.details_for_ids(evidence_ids, reasons)

    @staticmethod
    def internal_lineage_text(detail: Mapping[str, Any]) -> str:
        """Format database lineage consistently across all export formats."""
        locator = detail.get("locator") or {}
        scope = detail.get("scope") or {}
        parts = []
        table = scope.get("table") or locator.get("table")
        row_ids = scope.get("row_ids") or locator.get("row_ids")
        if table:
            parts.append(f"表 {table}")
        if row_ids:
            values = row_ids if isinstance(row_ids, list) else [row_ids]
            parts.append("行 " + ", ".join(str(item) for item in values))
        if scope.get("filters"):
            parts.append(
                "过滤 " + json.dumps(scope["filters"], ensure_ascii=False, sort_keys=True)
            )
        if scope.get("time_window"):
            parts.append(
                "范围 " + json.dumps(scope["time_window"], ensure_ascii=False, sort_keys=True)
            )
        retrieved = detail.get("retrieved_time") or scope.get("query_time")
        if retrieved:
            parts.append(f"检索于 {retrieved}")
        return "；".join(parts) or "已记录审计定位信息"
