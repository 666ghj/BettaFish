"""
章节装订器：负责把多个章节JSON合并为整本IR。

DocumentComposer 会注入缺失锚点、统一顺序，并补齐 IR 级元数据。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set

from ..ir import IR_VERSION


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
    ) -> Dict[str, object]:
        """
        把所有章节按order排序并注入唯一锚点，形成整本IR。

        同时合并 metadata/themeTokens/assets，供渲染器直接消费。
        """
        ordered = sorted(chapters, key=lambda c: c.get("order", 0))
        for idx, chapter in enumerate(ordered, start=1):
            chapter.setdefault("chapterId", f"S{idx}")
            anchor = chapter.get("anchor") or f"section-{idx}"
            chapter["anchor"] = self._ensure_unique_anchor(anchor)
            chapter.setdefault("order", idx * 10)

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
        }
        return document

    def _ensure_unique_anchor(self, anchor: str) -> str:
        """若存在重复锚点则追加序号，确保全局唯一。"""
        base = anchor
        counter = 2
        while anchor in self._seen_anchors:
            anchor = f"{base}-{counter}"
            counter += 1
        self._seen_anchors.add(anchor)
        return anchor


__all__ = ["DocumentComposer"]
