"""Stable, dependency-free provenance data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _string(value: Any) -> str:
    return "" if value is None else str(value)


@dataclass
class SourceRecord:
    source_id: str = ""
    agent: str = ""
    source_type: str = "unknown"
    title: str = ""
    url: str = ""
    platform: str = ""
    author: str = ""
    publish_time: str = ""
    retrieved_time: str = field(default_factory=utc_now_iso)
    locator: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "agent": self.agent,
            "source_type": self.source_type,
            "title": self.title,
            "url": self.url,
            "platform": self.platform,
            "author": self.author,
            "publish_time": self.publish_time,
            "retrieved_time": self.retrieved_time,
            "locator": dict(self.locator),
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SourceRecord":
        data = data or {}
        return cls(
            source_id=_string(data.get("source_id") or data.get("id")),
            agent=_string(data.get("agent")),
            source_type=_string(data.get("source_type") or data.get("type") or "unknown"),
            title=_string(data.get("title")),
            url=_string(data.get("url")),
            platform=_string(data.get("platform") or data.get("domain")),
            author=_string(data.get("author")),
            publish_time=_string(data.get("publish_time") or data.get("published_at")),
            retrieved_time=_string(data.get("retrieved_time") or data.get("retrieved_at") or utc_now_iso()),
            locator=_dict(data.get("locator")),
            meta=_dict(data.get("meta")),
        )


@dataclass
class EvidenceRecord:
    evidence_id: str = ""
    source_id: str = ""
    agent: str = ""
    evidence_type: str = "text"
    snippet: str = ""
    normalized_value: Any = None
    scope: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "agent": self.agent,
            "evidence_type": self.evidence_type,
            "snippet": self.snippet,
            "normalized_value": self.normalized_value,
            "scope": dict(self.scope),
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "EvidenceRecord":
        data = data or {}
        return cls(
            evidence_id=_string(data.get("evidence_id") or data.get("id")),
            source_id=_string(data.get("source_id")),
            agent=_string(data.get("agent")),
            evidence_type=_string(data.get("evidence_type") or data.get("type") or "text"),
            snippet=_string(data.get("snippet") or data.get("content")),
            normalized_value=data.get("normalized_value", data.get("value")),
            scope=_dict(data.get("scope")),
            meta=_dict(data.get("meta")),
        )


@dataclass
class ClaimRecord:
    claim_id: str = ""
    text: str = ""
    claim_type: str = "fact"
    evidence_ids: List[str] = field(default_factory=list)
    support_level: str = "unsupported"
    status: str = "unsupported"
    scope: Dict[str, Any] = field(default_factory=dict)
    text_span: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "claim_type": self.claim_type,
            "evidence_ids": list(self.evidence_ids),
            "support_level": self.support_level,
            "status": self.status,
            "support_status": self.status,
            "scope": dict(self.scope),
            "text_span": dict(self.text_span),
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ClaimRecord":
        data = data or {}
        status = _string(data.get("status") or data.get("support_status") or "unsupported")
        return cls(
            claim_id=_string(data.get("claim_id") or data.get("id")),
            text=_string(data.get("text")),
            claim_type=_string(data.get("claim_type") or data.get("type") or "fact").lower(),
            evidence_ids=[_string(item) for item in _list(data.get("evidence_ids") or data.get("citation_refs")) if _string(item)],
            support_level=_string(data.get("support_level") or status),
            status=status,
            scope=_dict(data.get("scope")),
            text_span=_dict(data.get("text_span")),
            meta=_dict(data.get("meta")),
        )


@dataclass
class ProvenanceBundle:
    bundle_id: str = ""
    agent: str = ""
    sources: List[SourceRecord] = field(default_factory=list)
    evidence: List[EvidenceRecord] = field(default_factory=list)
    claims: List[ClaimRecord] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    version: str = "1.0"
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def source_records(self) -> List[SourceRecord]:
        return self.sources

    @property
    def evidence_records(self) -> List[EvidenceRecord]:
        return self.evidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "agent": self.agent,
            "sources": [item.to_dict() for item in self.sources],
            "evidence": [item.to_dict() for item in self.evidence],
            "claims": [item.to_dict() for item in self.claims],
            "created_at": self.created_at,
            "version": self.version,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ProvenanceBundle":
        data = data or {}
        sources = data.get("sources", data.get("source_records", []))
        evidence = data.get("evidence", data.get("evidence_records", []))
        return cls(
            bundle_id=_string(data.get("bundle_id") or data.get("id")),
            agent=_string(data.get("agent")),
            sources=[SourceRecord.from_dict(item) for item in _list(sources) if isinstance(item, Mapping)],
            evidence=[EvidenceRecord.from_dict(item) for item in _list(evidence) if isinstance(item, Mapping)],
            claims=[ClaimRecord.from_dict(item) for item in _list(data.get("claims")) if isinstance(item, Mapping)],
            created_at=_string(data.get("created_at") or utc_now_iso()),
            version=_string(data.get("version") or "1.0"),
            meta=_dict(data.get("meta")),
        )

    def add_records(
        self,
        sources: Iterable[SourceRecord] = (),
        evidence: Iterable[EvidenceRecord] = (),
        claims: Iterable[ClaimRecord] = (),
    ) -> None:
        self.sources.extend(sources)
        self.evidence.extend(evidence)
        self.claims.extend(claims)
