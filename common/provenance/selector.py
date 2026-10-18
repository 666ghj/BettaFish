"""Chapter-scoped evidence selection for bounded generation prompts."""

from __future__ import annotations

import copy
from typing import Any, List, Mapping, Sequence, Tuple

from .models import EvidenceRecord, ProvenanceBundle
from .normalizer import dedupe_bundle, stable_id
from .relevance import flatten_text, meaningful_tokens
from .validators import gate_claims


class EvidenceSelector:
    def __init__(self, top_k: int = 8):
        self.top_k = max(1, int(top_k))

    def select(
        self,
        bundle: ProvenanceBundle | Mapping[str, Any] | None,
        *,
        chapter_topic: str,
        report_query: str = "",
        chapter_draft: str = "",
        claim_drafts: Sequence[str] | None = None,
        top_k: int | None = None,
    ) -> ProvenanceBundle:
        source_bundle = bundle if isinstance(bundle, ProvenanceBundle) else ProvenanceBundle.from_dict(bundle)
        # Selection ranks the candidate pool; strict source admission happens
        # at the report boundary so chapter generation can still rank raw
        # tool candidates that have not yet been enriched with a URL.
        source_bundle = dedupe_bundle(source_bundle)
        limit = max(1, int(top_k or self.top_k))
        query_text = " ".join(
            [
                report_query or "",
                chapter_topic or "",
                chapter_draft or "",
                " ".join(claim_drafts or []),
            ]
        ).strip()
        query_tokens = meaningful_tokens(query_text)
        source_index = {item.source_id: item for item in source_bundle.sources}

        ranked: List[Tuple[float, int, EvidenceRecord, List[str]]] = []
        for index, evidence in enumerate(source_bundle.evidence):
            source = source_index.get(evidence.source_id)
            candidate_text = " ".join(
                [
                    evidence.snippet,
                    flatten_text(evidence.scope),
                    flatten_text(evidence.meta.get("retrieval_contexts")),
                    flatten_text(evidence.normalized_value),
                    source.title if source else "",
                    source.platform if source else "",
                ]
            )
            candidate_tokens = meaningful_tokens(candidate_text)
            overlap = query_tokens & candidate_tokens
            score = float(len(overlap))
            reasons: List[str] = []
            if overlap:
                reasons.append("主题词匹配: " + "、".join(sorted(overlap)[:6]))
            lowered_candidate = candidate_text.lower()
            if chapter_topic and chapter_topic.lower() in lowered_candidate:
                score += 4.0
                reasons.append("直接匹配章节主题")
            contexts = evidence.meta.get("retrieval_contexts") or [evidence.scope]
            subjects = [
                item.get("subject") for item in contexts
                if isinstance(item, Mapping) and item.get("subject")
            ]
            if any(str(subject).lower() in query_text.lower() for subject in subjects):
                score += 2.0
                reasons.append("证据范围与章节主题一致")
            if not score:
                continue
            ranked.append((score, -index, evidence, reasons or ["作为当前章节的补充证据"] ))

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected_evidence = []
        selected_source_ids = set()
        selected_ids = set()
        for score, _, evidence, reasons in ranked[:limit]:
            cloned = copy.deepcopy(evidence)
            cloned.meta["selection_score"] = round(score, 4)
            cloned.meta["selection_reason"] = "；".join(reasons)
            selected_evidence.append(cloned)
            selected_source_ids.add(cloned.source_id)
            selected_ids.add(cloned.evidence_id)

        selected_claims, _ = gate_claims(
            [claim for claim in source_bundle.claims if set(claim.evidence_ids) & selected_ids],
            selected_ids,
        )
        return ProvenanceBundle(
            bundle_id=stable_id("bundle", source_bundle.bundle_id, chapter_topic, sorted(selected_ids)),
            agent=source_bundle.agent,
            sources=[copy.deepcopy(item) for item in source_bundle.sources if item.source_id in selected_source_ids],
            evidence=selected_evidence,
            claims=selected_claims,
            version=source_bundle.version,
            meta={
                "selection": {
                    "report_query": report_query,
                    "chapter_topic": chapter_topic,
                    "top_k": limit,
                    "pool_size": len(source_bundle.evidence),
                    "selected_size": len(selected_evidence),
                }
            },
        )
