"""Shared provenance identity checks for runtime and replay boundaries."""

from __future__ import annotations

from typing import Any, Mapping

from .models import ProvenanceBundle


ENGINE_AGENTS = {
    "query": "query_engine",
    "media": "media_engine",
    "insight": "insight_engine",
}


def metadata_identity_values(
    metadata: Mapping[str, Any] | None,
    singular: str,
    plural: str,
) -> list[str]:
    """Read a stable, de-duplicated identity list from singular/plural keys."""
    metadata = metadata or {}
    raw_values: list[Any] = []
    if metadata.get(singular) not in (None, ""):
        raw_values.append(metadata[singular])
    plural_value = metadata.get(plural)
    if isinstance(plural_value, (list, tuple, set)):
        raw_values.extend(plural_value)
    elif plural_value not in (None, ""):
        raw_values.append(plural_value)
    return list(
        dict.fromkeys(
            str(value).strip()
            for value in raw_values
            if str(value).strip()
        )
    )


def validate_bundle_query(
    bundle: ProvenanceBundle,
    expected_query: str = "",
    *,
    require_query: bool = False,
) -> str:
    """Reject a bundle that has no single authoritative report query."""
    queries = metadata_identity_values(bundle.meta, "query", "queries")
    if len(queries) > 1:
        raise ValueError(f"provenance bundle 包含多个查询主题：{'，'.join(queries)}")
    query = queries[0] if queries else ""
    if require_query and not query:
        raise ValueError("provenance bundle 缺少 meta.query")
    expected = str(expected_query or "").strip()
    if expected and query != expected:
        raise ValueError(
            f"报告查询与 provenance bundle 不一致：报告={expected}，bundle={query or '<missing>'}"
        )
    return query


def validate_bundle_run(
    bundle: ProvenanceBundle,
    expected_run_id: str = "",
    *,
    require_run: bool = False,
) -> str:
    """Reject a bundle that has no single authoritative runtime identity."""
    run_ids = metadata_identity_values(bundle.meta, "run_id", "run_ids")
    if len(run_ids) > 1:
        raise ValueError(
            f"provenance bundle 包含多个 run_id：{'，'.join(run_ids)}"
        )
    run_id = run_ids[0] if run_ids else ""
    if require_run and not run_id:
        raise ValueError("provenance bundle 缺少 meta.run_id")
    expected = str(expected_run_id or "").strip()
    if expected and run_id != expected:
        raise ValueError(
            f"运行任务与 provenance bundle 不一致："
            f"任务={expected}，bundle={run_id or '<missing>'}"
        )
    return run_id


def validate_bundle_agent(bundle: ProvenanceBundle, expected_agent: str) -> None:
    """Ensure the envelope and every attributed record belong to one engine."""
    expected = str(expected_agent or "").strip()
    if not expected or str(bundle.agent or "") != expected:
        raise ValueError(
            f"provenance bundle 与发布引擎不匹配："
            f"期望={expected or '<missing>'}，实际={bundle.agent or '<missing>'}"
        )
    for kind, records in (("source", bundle.sources), ("evidence", bundle.evidence)):
        missing = [
            record
            for record in records
            if not str(record.agent or "").strip()
        ]
        if missing:
            raise ValueError(
                f"provenance {kind} 记录缺少发布引擎身份：期望={expected}"
            )
        wrong = [
            str(record.agent)
            for record in records
            if str(record.agent or "") and str(record.agent) != expected
        ]
        if wrong:
            raise ValueError(
                f"provenance {kind} 记录与发布引擎不匹配："
                f"期望={expected}，实际={wrong[0]}"
            )


def validate_engine_bundles(
    bundles: Mapping[str, ProvenanceBundle],
    *,
    expected_query: str = "",
    require_query: bool = True,
    require_consistent_run: bool = True,
) -> dict[str, str]:
    """Validate query, engine and optional run identity across engine sidecars."""
    queries: dict[str, str] = {}
    run_ids: dict[str, str] = {}
    for engine, bundle in bundles.items():
        expected_agent = ENGINE_AGENTS.get(str(engine))
        if expected_agent is None:
            raise ValueError(f"不支持的 provenance 引擎：{engine}")
        try:
            validate_bundle_agent(bundle, expected_agent)
        except ValueError as exc:
            raise ValueError(f"{engine} 报告使用了错误的 provenance sidecar：{exc}") from exc
        query = validate_bundle_query(
            bundle,
            require_query=require_query,
        )
        if query:
            queries[str(engine)] = query

        run_id = validate_bundle_run(bundle)
        if run_id:
            run_ids[str(engine)] = run_id

    unique_queries = list(dict.fromkeys(queries.values()))
    if len(unique_queries) > 1:
        details = "，".join(f"{engine}={query}" for engine, query in queries.items())
        raise ValueError(f"三个 provenance sidecar 的查询主题不一致：{details}")
    authoritative_query = unique_queries[0] if unique_queries else ""
    explicit_query = str(expected_query or "").strip()
    if explicit_query and authoritative_query != explicit_query:
        raise ValueError(
            f"报告证据与当前查询不匹配（--query/报告主题与 provenance sidecar 不一致）："
            f"参数={explicit_query}，sidecar={authoritative_query or '<missing>'}"
        )

    if require_consistent_run and run_ids:
        if len(run_ids) != len(bundles):
            missing = sorted(set(bundles) - set(run_ids))
            raise ValueError(
                "provenance sidecar 的 run_id 信息不完整："
                f"缺少 {', '.join(missing)}"
            )
        unique_run_ids = list(dict.fromkeys(run_ids.values()))
        if len(unique_run_ids) > 1:
            details = "，".join(
                f"{engine}={run_id}" for engine, run_id in run_ids.items()
            )
            raise ValueError(f"provenance sidecar 来自不同运行轮次：{details}")

    return {
        "query": authoritative_query,
        "run_id": next(iter(run_ids.values()), ""),
    }


__all__ = [
    "ENGINE_AGENTS",
    "metadata_identity_values",
    "validate_bundle_agent",
    "validate_bundle_query",
    "validate_bundle_run",
    "validate_engine_bundles",
]
