"""文件名清洗工具，避免导出路径穿越和响应头注入。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional


def safe_filename_segment(value: Any, fallback: str = "report") -> str:
    """
    生成可用于文件名的安全片段，仅保留字母数字与常见分隔符。

    参数:
        value: 原始字符串。
        fallback: 清洗后为空时使用的回退值。
    """
    sanitized = "".join(c for c in str(value) if c.isalnum() or c in (" ", "-", "_")).strip()
    sanitized = sanitized.replace(" ", "_")
    return sanitized or fallback


def topic_from_document_ir(document_ir: Any, fallback: str = "report") -> str:
    """
    从 Document IR 中取出用于命名的主题，缺失时回退到 fallback。
    """
    metadata = document_ir.get("metadata") if isinstance(document_ir, Mapping) else None
    if not isinstance(metadata, Mapping):
        metadata = {}
    topic = metadata.get("topic") or metadata.get("title") or metadata.get("query")
    if topic is None or not str(topic).strip():
        return fallback
    return str(topic)


def report_export_filename(
    document_ir: Any,
    extension: str,
    fallback: str = "report",
    timestamp: Optional[str] = None,
) -> str:
    """
    生成 report_<topic>_<timestamp>.<ext> 形式的安全导出文件名。
    """
    topic = topic_from_document_ir(document_ir, fallback=fallback)
    safe_topic = safe_filename_segment(topic, fallback=fallback)
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = extension.lstrip(".")
    return f"report_{safe_topic}_{stamp}.{ext}"
