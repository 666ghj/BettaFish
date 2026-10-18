"""Audit/replay sidecar persistence; runtime code passes bundles directly."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Type, TypeVar, Union

from loguru import logger

from .models import ProvenanceBundle


PathLike = Union[str, Path]
EngineStateT = TypeVar("EngineStateT")


def sidecar_path(report_path: PathLike) -> Path:
    return Path(report_path).with_suffix(".provenance.json")


def atomic_write_text(path: PathLike, content: str) -> Path:
    """Atomically replace one UTF-8 text file and clean interrupted temps."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write(str(content))
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return target


def save_sidecar(bundle: ProvenanceBundle, report_path: PathLike) -> Path:
    target = sidecar_path(report_path)
    payload = json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2)
    return atomic_write_text(target, payload)


def save_engine_report(
    report_content: str,
    *,
    query: str,
    output_dir: PathLike,
    bundle: ProvenanceBundle,
    state: Any = None,
    save_intermediate_state: bool = False,
) -> Dict[str, Path]:
    """Persist one engine report, its provenance sidecar, and optional state."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    artifact_id = uuid.uuid4().hex[:8]
    query_safe = "".join(
        char for char in str(query or "") if char.isalnum() or char in (" ", "-", "_")
    ).rstrip()
    query_safe = query_safe.replace(" ", "_")[:30] or "report"
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    report_path = directory / f"deep_search_report_{query_safe}_{timestamp}_{artifact_id}.md"
    atomic_write_text(report_path, report_content)
    provenance_path = save_sidecar(bundle, report_path)

    result = {"report": report_path, "provenance": provenance_path}
    logger.info(f"报告已保存到: {report_path}")
    logger.info(f"证据审计文件已保存到: {provenance_path}")
    if save_intermediate_state and state is not None:
        state_path = directory / f"state_{query_safe}_{timestamp}_{artifact_id}.json"
        if hasattr(state, "to_json"):
            atomic_write_text(state_path, state.to_json())
        else:
            state.save_to_file(str(state_path))
        result["state"] = state_path
        logger.info(f"状态已保存到: {state_path}")
    return result


def restore_engine_state(
    state_type: Type[EngineStateT],
    paragraph_type: Type[Any],
    data: Dict[str, Any],
) -> EngineStateT:
    """Restore the fields shared by Query, Media, and Insight engine states."""
    paragraphs = [paragraph_type.from_dict(item) for item in data.get("paragraphs", [])]
    return state_type(
        query=data.get("query", ""),
        report_title=data.get("report_title", ""),
        paragraphs=paragraphs,
        final_report=data.get("final_report", ""),
        provenance_bundle=ProvenanceBundle.from_dict(data.get("provenance_bundle")),
        is_completed=data.get("is_completed", False),
        created_at=data.get("created_at", datetime.now().isoformat()),
        updated_at=data.get("updated_at", datetime.now().isoformat()),
    )


def serialize_engine_state(state: Any) -> Dict[str, Any]:
    """Serialize fields shared by Query, Media, and Insight engine states."""
    return {
        "query": state.query,
        "report_title": state.report_title,
        "paragraphs": [paragraph.to_dict() for paragraph in state.paragraphs],
        "final_report": state.final_report,
        "provenance_bundle": state.provenance_bundle.to_dict(),
        "is_completed": state.is_completed,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def load_sidecar(path_or_report: PathLike) -> ProvenanceBundle:
    path = Path(path_or_report)
    target = path if path.name.endswith(".provenance.json") else sidecar_path(path)
    if not target.exists():
        return ProvenanceBundle()
    return ProvenanceBundle.from_dict(json.loads(target.read_text(encoding="utf-8")))
