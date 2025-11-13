"""
根据模板目录与多源报告，生成整本报告的标题/目录/主题设计。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from loguru import logger

from ..core import TemplateSection
from ..prompts import (
    SYSTEM_PROMPT_DOCUMENT_LAYOUT,
    build_document_layout_prompt,
)
from .base_node import BaseNode


class DocumentLayoutNode(BaseNode):
    """负责生成全局标题、目录与Hero设计"""

    def __init__(self, llm_client):
        super().__init__(llm_client, "DocumentLayoutNode")

    def run(
        self,
        sections: List[TemplateSection],
        template_markdown: str,
        reports: Dict[str, str],
        forum_logs: str,
        query: str,
        template_overview: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """综合模板+多源内容，生成全书的标题、目录结构与主题色板"""
        # 将模板原文、切片结构与多源报告一并喂给LLM，便于其理解层级与素材
        payload = {
            "query": query,
            "template": {
                "raw": template_markdown,
                "sections": [section.to_dict() for section in sections],
            },
            "templateOverview": template_overview
            or {
                "title": sections[0].title if sections else "",
                "chapters": [section.to_dict() for section in sections],
            },
            "reports": reports,
            "forumLogs": forum_logs,
        }

        user_message = build_document_layout_prompt(payload)
        response = self.llm_client.stream_invoke_to_string(
            SYSTEM_PROMPT_DOCUMENT_LAYOUT,
            user_message,
            temperature=0.3,
            top_p=0.9,
        )
        design = self._parse_response(response)
        logger.info("文档标题/目录设计已生成")
        return design

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """解析LLM返回的JSON文本，若失败则抛出友好错误"""
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError("文档设计LLM返回空内容")
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"文档设计JSON解析失败: {exc}") from exc


__all__ = ["DocumentLayoutNode"]
