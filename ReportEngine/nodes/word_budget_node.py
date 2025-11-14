"""
章节篇幅规划节点。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from loguru import logger

from ..core import TemplateSection
from ..prompts import (
    SYSTEM_PROMPT_WORD_BUDGET,
    build_word_budget_prompt,
)
from .base_node import BaseNode


class WordBudgetNode(BaseNode):
    """
    规划各章节字数与重点。

    输出总字数、全局写作准则以及每章/小节的 target/min/max 字数约束。
    """

    def __init__(self, llm_client):
        """仅记录LLM客户端引用，方便run阶段发起请求"""
        super().__init__(llm_client, "WordBudgetNode")

    def run(
        self,
        sections: List[TemplateSection],
        design: Dict[str, Any],
        reports: Dict[str, str],
        forum_logs: str,
        query: str,
        template_overview: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        根据设计稿和所有素材规划章节字数，让LLM写作时有明确篇幅目标。

        参数:
            sections: 模板章节列表。
            design: 布局节点返回的设计稿（title/toc/hero等）。
            reports: 三引擎报告映射。
            forum_logs: 论坛日志原文。
            query: 用户查询词。
            template_overview: 可选的模板概览，含章节元信息。

        返回:
            dict: 章节篇幅规划结果，包含 `totalWords`、`globalGuidelines` 与逐章 `chapters`。
        """
        # 输入中除了章节骨架外，还包含布局节点输出，方便约束篇幅时参考视觉主次
        payload = {
            "query": query,
            "design": design,
            "sections": [section.to_dict() for section in sections],
            "templateOverview": template_overview
            or {
                "title": sections[0].title if sections else "",
                "chapters": [section.to_dict() for section in sections],
            },
            "reports": reports,
            "forumLogs": forum_logs,
        }
        user = build_word_budget_prompt(payload)
        response = self.llm_client.stream_invoke_to_string(
            SYSTEM_PROMPT_WORD_BUDGET,
            user,
            temperature=0.25,
            top_p=0.85,
        )
        plan = self._parse_response(response)
        logger.info("章节字数规划已生成")
        return plan

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """
        将LLM输出的JSON文本转为字典，失败时提示规划异常。

        参数:
            raw: LLM返回值，可能包含```包裹。

        返回:
            dict: 合法的篇幅规划JSON。

        异常:
            ValueError: 当响应为空或JSON解析失败时抛出。
        """
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError("篇幅规划LLM返回空内容")
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"篇幅规划JSON解析失败: {exc}") from exc


__all__ = ["WordBudgetNode"]
