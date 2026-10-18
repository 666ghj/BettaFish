"""
章节装订器：负责把多个章节JSON合并为整本IR。

DocumentComposer 会注入缺失锚点、统一顺序，并补齐 IR 级元数据。
"""

from __future__ import annotations

from datetime import datetime
import copy
from typing import Any, Dict, List, Mapping, Optional, Set

from ..ir import IR_VERSION
from common.provenance.models import ClaimRecord, ProvenanceBundle
from common.provenance.normalizer import merge_bundles
from common.provenance.validators import filter_valid_evidence, gate_claims, sanitize_blocks


class DocumentComposer:
    """
    将章节拼接成Document IR的简单装订器。

    作用：
        - 按order排序章节，补充默认chapterId；
        - 防止anchor重复，生成全局唯一锚点；
        - 注入 IR 版本与生成时间戳。
    """

    def __init__(self):
        """初始化装订器并记录已使用的锚点，避免重复"""
        self._seen_anchors: Set[str] = set()

    def build_document(
        self,
        report_id: str,
        metadata: Dict[str, object],
        chapters: List[Dict[str, object]],
        provenance_bundle: Optional[ProvenanceBundle | Mapping[str, Any] | List[Any]] = None,
    ) -> Dict[str, object]:
        """
        把所有章节按order排序并注入唯一锚点，形成整本IR。

        同时合并 metadata/themeTokens/assets，供渲染器直接消费。

        参数:
            report_id: 本次报告ID。
            metadata: 全局元信息（标题、主题、toc等）。
            chapters: 章节payload列表。

        返回:
            dict: 满足渲染器需求的Document IR。
        """
        # 构建从chapterId到toc anchor的映射
        self._seen_anchors.clear()
        toc_anchor_map = self._build_toc_anchor_map(metadata)

        ordered = sorted(copy.deepcopy(chapters), key=lambda c: c.get("order", 0))
        for idx, chapter in enumerate(ordered, start=1):
            chapter.setdefault("chapterId", f"S{idx}")

            # 优先级：1. 目录配置的anchor 2. 章节自带的anchor 3. 默认anchor
            chapter_id = chapter.get("chapterId")
            anchor = (
                toc_anchor_map.get(chapter_id) or
                chapter.get("anchor") or
                f"section-{idx}"
            )
            chapter["anchor"] = self._ensure_unique_anchor(anchor)
            chapter.setdefault("order", idx * 10)
            if chapter.get("errorPlaceholder"):
                self._ensure_heading_block(chapter)

        if isinstance(provenance_bundle, list):
            merged_bundle = merge_bundles(provenance_bundle)
        elif isinstance(provenance_bundle, ProvenanceBundle):
            merged_bundle = copy.deepcopy(provenance_bundle)
        elif isinstance(provenance_bundle, Mapping):
            merged_bundle = ProvenanceBundle.from_dict(copy.deepcopy(provenance_bundle))
        else:
            merged_bundle = ProvenanceBundle(agent="report_engine")

        merged_bundle = filter_valid_evidence(merged_bundle)
        if provenance_bundle is not None:
            # This overview is built by the server from TemplateSection values,
            # before chapter generation.  Model-written headings have no such
            # authority and must pass the normal claim gate.
            template_sections = {
                str(section.get("chapterId")): section
                for section in (metadata.get("templateOverview") or {}).get("chapters", [])
                if isinstance(section, Mapping) and section.get("chapterId")
            }
            for chapter in ordered:
                # Provenance is rendered and indexed at block level.  Model
                # output occasionally puts the same fields on the chapter
                # root, where they are neither rendered nor collected into
                # claimIndex; retaining them would create dangling claims.
                for field in ("claims", "citation_refs", "support_status"):
                    chapter.pop(field, None)
                section = template_sections.get(str(chapter.get("chapterId")), {})
                trusted_headings = (section.get("title", ""), *(section.get("outline") or []))
                chapter["blocks"] = sanitize_blocks(
                    chapter.get("blocks", []), merged_bundle,
                    trusted_headings=trusted_headings,
                )
                if not chapter["blocks"]:
                    self._ensure_heading_block(chapter)
        self._normalize_duplicate_claim_ids(ordered)
        chapter_claims: List[ClaimRecord] = []
        for chapter in ordered:
            self._collect_nested_claims(chapter.get("blocks", []), chapter_claims)
        accepted_claims, _ = gate_claims(
            chapter_claims, merged_bundle
        )
        merged_bundle.claims = self._dedupe_claims(accepted_claims)

        document = {
            "version": IR_VERSION,
            "reportId": report_id,
            "metadata": {
                **metadata,
                "generatedAt": metadata.get("generatedAt")
                or datetime.utcnow().isoformat() + "Z",
            },
            "themeTokens": metadata.get("themeTokens", {}),
            "chapters": ordered,
            "assets": metadata.get("assets", {}),
            "provenanceBundle": merged_bundle.to_dict(),
            "provenanceIndex": {
                "sources": {item.source_id: item.to_dict() for item in merged_bundle.sources},
                "evidence": {item.evidence_id: item.to_dict() for item in merged_bundle.evidence},
            },
            "claimIndex": {item.claim_id: item.to_dict() for item in merged_bundle.claims},
            "provenanceEnforced": provenance_bundle is not None,
        }
        return document

    def _normalize_duplicate_claim_ids(self, chapters: List[Dict[str, object]]) -> None:
        """Namespace repeated model-generated IDs and mutate the owning blocks."""
        seen: Set[str] = set()

        def visit(blocks: Any, chapter_id: str) -> None:
            if not isinstance(blocks, list):
                return
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                for claim in block.get("claims", []) or []:
                    if not isinstance(claim, dict):
                        continue
                    claim_id = str(claim.get("claim_id") or "")
                    if not claim_id:
                        continue
                    candidate = claim_id
                    if candidate in seen:
                        base = f"{chapter_id}--{claim_id}"
                        candidate = base
                        suffix = 2
                        while candidate in seen:
                            candidate = f"{base}-{suffix}"
                            suffix += 1
                        claim["claim_id"] = candidate
                    seen.add(candidate)
                visit(block.get("blocks"), chapter_id)
                for item in block.get("items", []) or []:
                    visit(item, chapter_id)
                for row in block.get("rows", []) or []:
                    if not isinstance(row, dict):
                        continue
                    for cell in row.get("cells", []) or []:
                        if isinstance(cell, dict):
                            visit(cell.get("blocks"), chapter_id)

        for chapter in chapters:
            visit(chapter.get("blocks"), str(chapter.get("chapterId") or "chapter"))


    def _collect_nested_claims(self, blocks: Any, claims: List[ClaimRecord]) -> None:
        if not isinstance(blocks, list):
            return
        for block in blocks:
            if not isinstance(block, dict):
                continue
            claims.extend(
                ClaimRecord.from_dict(item)
                for item in block.get("claims", []) or []
                if isinstance(item, Mapping)
            )
            self._collect_nested_claims(block.get("blocks"), claims)
            for item in block.get("items", []) or []:
                self._collect_nested_claims(item, claims)
            for row in block.get("rows", []) or []:
                if not isinstance(row, dict):
                    continue
                for cell in row.get("cells", []) or []:
                    if isinstance(cell, dict):
                        self._collect_nested_claims(cell.get("blocks"), claims)

    @staticmethod
    def _dedupe_claims(claims: List[ClaimRecord]) -> List[ClaimRecord]:
        result: List[ClaimRecord] = []
        seen = set()
        for claim in claims:
            key = claim.claim_id or (claim.claim_type, claim.text, tuple(claim.evidence_ids))
            if key in seen:
                continue
            seen.add(key)
            result.append(claim)
        return result

    def _ensure_unique_anchor(self, anchor: str) -> str:
        """若存在重复锚点则追加序号，确保全局唯一。"""
        base = anchor
        counter = 2
        while anchor in self._seen_anchors:
            anchor = f"{base}-{counter}"
            counter += 1
        self._seen_anchors.add(anchor)
        return anchor

    def _build_toc_anchor_map(self, metadata: Dict[str, object]) -> Dict[str, str]:
        """
        从metadata.toc.customEntries构建chapterId到anchor的映射。

        参数:
            metadata: 文档元信息。

        返回:
            dict: chapterId -> anchor 的映射。
        """
        toc_config = metadata.get("toc") or {}
        custom_entries = toc_config.get("customEntries") or []
        anchor_map = {}

        for entry in custom_entries:
            if isinstance(entry, dict):
                chapter_id = entry.get("chapterId")
                anchor = entry.get("anchor")
                if chapter_id and anchor:
                    anchor_map[chapter_id] = anchor

        return anchor_map

    def _ensure_heading_block(self, chapter: Dict[str, object]) -> None:
        """保证占位章节仍然拥有可用于目录的heading block。"""
        blocks = chapter.get("blocks")
        if isinstance(blocks, list):
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "heading":
                    return
        heading = {
            "type": "heading",
            "level": 2,
            "text": chapter.get("title") or "占位章节",
            "anchor": chapter.get("anchor"),
        }
        if isinstance(blocks, list):
            blocks.insert(0, heading)
        else:
            chapter["blocks"] = [heading]


__all__ = ["DocumentComposer"]
