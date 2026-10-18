"""Bounded, per-run in-memory transport between Streamlit workers and Flask."""

from __future__ import annotations

import copy
import ipaddress
import json
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from .identity import (
    validate_bundle_agent,
    validate_bundle_query,
    validate_bundle_run,
)
from .models import ProvenanceBundle, utc_now_iso
from .normalizer import merge_bundles
from .validators import filter_valid_evidence


ENGINE_ORDER = ("query", "media", "insight")
_ENGINE_SET = frozenset(ENGINE_ORDER)
_MAX_EVIDENCE_IDS = 200
_MAX_EVIDENCE_ID_LENGTH = 256


class RuntimeCapacityError(RuntimeError):
    """Raised when every bounded runtime slot still belongs to an active run."""


def _normalize_engine_list(engines) -> list[str]:
    """Validate and canonicalize the engine selection for one runtime run."""
    if engines is None:
        return list(ENGINE_ORDER)
    if isinstance(engines, (str, bytes, Mapping)) or not isinstance(
        engines, (list, tuple, set, frozenset)
    ):
        raise ValueError("engines 必须是 query/media/insight 名称列表")

    normalized: list[str] = []
    unknown: list[str] = []
    duplicates: list[str] = []
    for value in engines:
        if not isinstance(value, str):
            unknown.append(str(value))
            continue
        engine = value.strip().lower()
        if engine not in _ENGINE_SET:
            unknown.append(engine or "<empty>")
        elif engine in normalized:
            duplicates.append(engine)
        else:
            normalized.append(engine)
    if unknown:
        raise ValueError(f"engines 包含不支持的引擎：{', '.join(unknown[:5])}")
    if duplicates:
        raise ValueError(f"engines 包含重复引擎：{', '.join(duplicates[:5])}")
    if not normalized:
        raise ValueError("engines 不能为空")
    return [engine for engine in ENGINE_ORDER if engine in normalized]


def _normalize_evidence_ids(value, *, limit: int | None = _MAX_EVIDENCE_IDS) -> list[str]:
    """Accept only a collection of IDs; strings must never become char IDs."""
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(
        value, (list, tuple, set, frozenset)
    ):
        return []
    result: list[str] = []
    for item in value:
        candidate = str(item or "").strip()
        if not candidate or len(candidate) > _MAX_EVIDENCE_ID_LENGTH:
            continue
        if candidate not in result:
            result.append(candidate)
        if limit is not None and len(result) >= limit:
            break
    return result


class RuntimeProvenanceStore:
    def __init__(
        self,
        max_runs: int = 32,
        *,
        active_ttl_seconds: float = 6 * 60 * 60,
        terminal_ttl_seconds: float = 60 * 60,
        clock=time.monotonic,
    ):
        self.max_runs = int(max_runs)
        if self.max_runs < 1:
            raise ValueError("max_runs 必须大于 0")
        self.active_ttl_seconds = float(active_ttl_seconds)
        self.terminal_ttl_seconds = float(terminal_ttl_seconds)
        if self.active_ttl_seconds <= 0 or self.terminal_ttl_seconds <= 0:
            raise ValueError("运行任务 TTL 必须大于 0")
        self._clock = clock
        self._runs = OrderedDict()
        self._lock = threading.RLock()

    @staticmethod
    def _engine_is_terminal(entry: dict | None) -> bool:
        return bool(entry and (entry.get("complete") or entry.get("failed")))

    def _purge_expired_locked(self) -> None:
        now = self._clock()
        expired = []
        for run_id, run in self._runs.items():
            age = now - float(run.get("_updated_at", run.get("_created_at", now)))
            ttl = (
                self.terminal_ttl_seconds
                if self._is_terminal(run)
                else self.active_ttl_seconds
            )
            if age >= ttl:
                expired.append(run_id)
        for run_id in expired:
            del self._runs[run_id]
            _cleanup_runtime_forum_files(run_id)

    def begin(
        self,
        query: str,
        engines=None,
    ) -> str:
        expected = _normalize_engine_list(engines)
        query = str(query or "").strip()
        if not query:
            raise ValueError("查询不能为空")
        run_id = uuid.uuid4().hex
        with self._lock:
            self._purge_expired_locked()
            while len(self._runs) >= self.max_runs:
                removable = next(
                    (
                        key
                        for key, value in self._runs.items()
                        if self._is_terminal(value)
                    ),
                    None,
                )
                if removable is None:
                    raise RuntimeCapacityError(
                        f"运行任务容量已满（最多 {self.max_runs} 个活跃任务），请等待已有任务完成"
                    )
                del self._runs[removable]
                _cleanup_runtime_forum_files(removable)
            now = self._clock()
            self._runs[run_id] = {
                "query": query,
                "expected": expected,
                "engines": {},
                "_created_at": now,
                "_updated_at": now,
            }
        return run_id

    @staticmethod
    def _is_terminal(run: dict) -> bool:
        entries = run.get("engines", {})
        return all(
            entries.get(engine, {}).get("complete")
            or entries.get(engine, {}).get("failed")
            for engine in run.get("expected", [])
        )

    def publish(self, run_id: str, engine: str, query: str, report: str, bundle, complete: bool = True):
        engine = _normalize_engine_list([engine])[0]
        query = str(query or "").strip()
        with self._lock:
            self._purge_expired_locked()
            run = self._runs.get(run_id)
            if not run or query != run["query"] or engine not in run["expected"]:
                raise ValueError("运行任务不存在，或查询/引擎不匹配")
            if self._engine_is_terminal(run["engines"].get(engine)):
                return False
            provenance = ProvenanceBundle.from_dict(bundle.to_dict() if isinstance(bundle, ProvenanceBundle) else bundle)
            validate_bundle_agent(provenance, f"{engine}_engine")
            validate_bundle_query(provenance, query, require_query=True)
            validate_bundle_run(provenance, run_id, require_run=True)
            provenance.meta.update({"run_id": run_id, "query": query})
            # Empty evidence is an explicit result, never a request to reload old sidecars.
            run["engines"][engine] = {
                "report": str(report),
                "bundle": filter_valid_evidence(provenance),
                "complete": bool(complete),
                "failed": False,
            }
            run["_updated_at"] = self._clock()
            return True

    def fail(self, run_id: str, engine: str, query: str, error: str):
        engine = _normalize_engine_list([engine])[0]
        query = str(query or "").strip()
        with self._lock:
            self._purge_expired_locked()
            run = self._runs.get(run_id)
            if not run or query != run["query"] or engine not in run["expected"]:
                raise ValueError("运行任务不存在，或查询/引擎不匹配")
            if self._engine_is_terminal(run["engines"].get(engine)):
                return False
            run["engines"][engine] = {
                "report": "",
                "bundle": ProvenanceBundle(agent=f"{engine}_engine"),
                "complete": False,
                "failed": True,
                "error": str(error or "未知错误"),
            }
            run["_updated_at"] = self._clock()
            return True

    def discard(self, run_id: str) -> bool:
        """Explicitly release an abandoned run without affecting other runs."""
        with self._lock:
            normalized = str(run_id or "")
            removed = self._runs.pop(normalized, None) is not None
            if removed:
                _cleanup_runtime_forum_files(normalized)
            return removed

    def context(self, run_id: str) -> dict:
        """Return immutable per-run metadata needed by downstream readers."""
        with self._lock:
            self._purge_expired_locked()
            run = self._runs.get(run_id)
            if not run:
                raise ValueError("运行任务已过期或不存在")
            return {
                "query": run["query"],
                "expected": list(run["expected"]),
            }

    def status(self, run_id: str) -> dict:
        with self._lock:
            self._purge_expired_locked()
            run = self._runs.get(run_id)
            if not run:
                return {"ready": False, "missing_files": ["runtime task expired or unknown"], "latest_files": {}}
            failed = {
                engine: run["engines"][engine].get("error", "未知错误")
                for engine in run["expected"]
                if run["engines"].get(engine, {}).get("failed")
            }
            missing = [
                engine
                for engine in run["expected"]
                if not run["engines"].get(engine, {}).get("complete")
                and engine not in failed
            ]
            return {
                "ready": not missing and not failed,
                "missing_files": missing,
                "failed": failed,
                "latest_files": {},
                "transport": "runtime",
            }

    def inputs(self, run_id: str, query: str, forum_logs: str = "") -> dict:
        with self._lock:
            self._purge_expired_locked()
            status = self.status(run_id)
            if status.get("failed"):
                raise ValueError(f"本轮 Agent 运行失败: {status['failed']}")
            if not status["ready"]:
                raise ValueError("本轮 Agent 尚未全部提交运行态结果")
            run = self._runs[run_id]
            if query != run["query"]:
                raise ValueError("报告查询与本轮任务不匹配")
            entries = run["engines"]
            merged_bundle = merge_bundles(
                [
                    copy.deepcopy(entries[engine]["bundle"])
                    for engine in ENGINE_ORDER
                    if engine in entries
                ]
            )
            merged_bundle.meta.update({"run_id": run_id, "query": query})
            return {
                "reports": [entries.get(engine, {}).get("report", "") for engine in ENGINE_ORDER],
                "provenance_bundle": merged_bundle,
                "forum_logs": str(forum_logs or ""),
            }


runtime_store = RuntimeProvenanceStore()


_RUNTIME_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_RUNTIME_FORUM_LOCK = threading.RLock()


def _runtime_forum_path(run_id: str, engine: str) -> Path:
    run_id = str(run_id or "")
    engine = str(engine or "").lower()
    if not _RUNTIME_SEGMENT_RE.fullmatch(run_id) or engine not in ENGINE_ORDER:
        raise ValueError("非法的运行任务或引擎标识")
    return Path("logs") / "forum_runs" / run_id / f"{engine}.jsonl"


def _cleanup_runtime_forum_files(run_id: str) -> None:
    """Remove only the known files belonging to one validated runtime run."""
    try:
        paths = [_runtime_forum_path(run_id, engine) for engine in ENGINE_ORDER]
    except ValueError:
        return
    with _RUNTIME_FORUM_LOCK:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        run_dir = paths[0].parent
        try:
            run_dir.rmdir()
        except OSError:
            pass
        try:
            run_dir.parent.rmdir()
        except OSError:
            pass


def append_runtime_forum_message(
    run_id: str,
    engine: str,
    content: str,
    referenced_evidence_ids=(),
) -> bool:
    """Append one source-labelled, run-scoped Agent summary as JSONL."""
    content = str(content or "").strip()
    refs = _normalize_evidence_ids(referenced_evidence_ids)
    # Unsupported generated summaries are not useful forum context.
    if not content or not refs:
        return False
    path = _runtime_forum_path(run_id, engine)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": str(run_id),
        "engine": str(engine).lower(),
        "source": f"{str(engine).upper()}_ENGINE",
        "timestamp": utc_now_iso(),
        "content": content[:20000],
        "referenced_evidence_ids": refs,
    }
    with _RUNTIME_FORUM_LOCK:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
            stream.flush()
    return True


def read_runtime_forum_context(
    run_id: str,
    allowed_evidence_ids=None,
) -> str:
    """Read only forum summaries carrying the requested run ID."""
    allowed = (
        set(_normalize_evidence_ids(allowed_evidence_ids, limit=None))
        if allowed_evidence_ids is not None
        else None
    )
    messages = []
    for engine in ENGINE_ORDER:
        path = _runtime_forum_path(run_id, engine)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                item = json.loads(line)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict):
                continue
            if item.get("run_id") != run_id or item.get("engine") != engine:
                continue
            content = str(item.get("content") or "").strip()
            refs = _normalize_evidence_ids(item.get("referenced_evidence_ids", []))
            if allowed is not None:
                refs = [value for value in refs if value in allowed]
            if content and refs:
                messages.append(
                    (
                        str(item.get("timestamp") or ""),
                        str(item.get("source") or f"{engine.upper()}_ENGINE"),
                        content,
                        refs,
                    )
                )
    messages.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(
        f"[{timestamp}] [{source}] "
        f"[EVIDENCE_IDS:{json.dumps(refs, ensure_ascii=False)}] {content}"
        for timestamp, source, content, refs in messages
    )


def _publish_runtime_payload(payload: dict, *, attempts: int = 2):
    endpoint = os.environ.get("BETTAFISH_PROVENANCE_ENDPOINT", "")
    if not payload.get("run_id") or not endpoint:
        return False
    parsed_endpoint = urlsplit(endpoint)
    hostname = parsed_endpoint.hostname or ""
    try:
        is_loopback = hostname.lower() == "localhost" or ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = False
    if parsed_endpoint.scheme not in {"http", "https"} or not is_loopback:
        raise RuntimeError("运行态证据提交端点必须是本机回环地址")

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error = None
    # The payload contains the callback token, report and evidence bundle.  It
    # must never inherit HTTP(S)_PROXY on its way to the local Flask process.
    opener = build_opener(ProxyHandler({}))
    for attempt in range(max(1, attempts)):
        request = Request(endpoint, data=body, headers={
            "Content-Type": "application/json",
            "X-Provenance-Token": os.environ.get("BETTAFISH_PROVENANCE_TOKEN", ""),
        }, method="POST")
        try:
            with opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise RuntimeError("运行态证据提交失败")
                raw_response = response.read()
                if isinstance(raw_response, bytes):
                    raw_response = raw_response.decode("utf-8", errors="replace")
                try:
                    response_payload = json.loads(str(raw_response or ""))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise RuntimeError("运行态证据提交响应不是有效 JSON") from exc
                if not isinstance(response_payload, dict) or response_payload.get("success") is not True:
                    detail = ""
                    if isinstance(response_payload, dict):
                        detail = str(
                            response_payload.get("error")
                            or response_payload.get("message")
                            or ""
                        ).strip()
                    suffix = f": {detail[:200]}" if detail else ""
                    raise RuntimeError(f"运行态证据提交未确认成功{suffix}")
            return True
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max(1, attempts):
                time.sleep(0.2)
    raise RuntimeError(f"运行态证据提交失败: {last_error}") from last_error


def publish_runtime_result(run_id: str, engine: str, query: str, report: str, bundle: ProvenanceBundle):
    """Publish through the parent's loopback endpoint; standalone CLI has no endpoint."""
    return _publish_runtime_payload({
        "run_id": run_id,
        "engine": engine,
        "query": query,
        "report": report,
        "bundle": bundle.to_dict(),
        "status": "complete",
    })


def publish_runtime_failure(run_id: str, engine: str, query: str, error: str):
    """Expose an engine terminal failure so ReportEngine does not wait forever."""
    return _publish_runtime_payload({
        "run_id": run_id,
        "engine": engine,
        "query": query,
        "error": str(error),
        "status": "failed",
    }, attempts=1)
