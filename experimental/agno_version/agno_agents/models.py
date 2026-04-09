# agno_agents/models.py
# 三个 Agent 共享的结构化输出模型
# ForumEngine / ReportEngine 依赖这些模型解析 Agent 的中间和最终输出

import json as _json
import re as _re

from pydantic import BaseModel, Field
from typing import List, Optional


class SearchDecision(BaseModel):
    """搜索决策（对应原 FirstSearchNode / ReflectionNode 输出）"""
    search_query: str = Field(description="搜索关键词")
    search_tool: str = Field(description="选用的搜索工具名称")
    reasoning: str = Field(description="选择该工具和关键词的理由")
    start_date: Optional[str] = Field(None, description="开始日期，格式YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期，格式YYYY-MM-DD")
    platform: Optional[str] = Field(None, description="平台名称，如 bilibili, weibo, douyin 等")
    time_period: Optional[str] = Field(None, description="时间周期，如 24h, week, year")
    enable_sentiment: Optional[bool] = Field(True, description="是否启用情感分析")
    texts: Optional[List[str]] = Field(None, description="文本列表，仅用于 analyze_sentiment")


class ParagraphOutline(BaseModel):
    """报告段落大纲（对应原 ReportStructureNode 输出的每个元素）"""
    title: str = Field(description="段落标题")
    content: str = Field(description="段落预期内容描述")


class ReportStructure(BaseModel):
    """报告结构规划（对应原 ReportStructureNode 完整输出）"""
    paragraphs: List[ParagraphOutline] = Field(description="报告段落列表，最多5个")


class ParagraphResult(BaseModel):
    """单个段落的分析结果（对应原 FirstSummaryNode / ReflectionSummaryNode 输出）"""
    title: str = Field(description="段落标题")
    paragraph_latest_state: str = Field(description="段落最新内容（800-1500字）")


class AnalysisResult(BaseModel):
    """Agent 完整分析结果（ForumEngine / ReportEngine 消费此结构）"""
    query: str = Field(description="原始分析主题")
    paragraphs: List[ParagraphResult] = Field(description="各段落分析结果")
    final_report: str = Field(description="最终格式化的完整 Markdown 报告")


def parse_analysis_result(content: str, query: str) -> AnalysisResult:
    """
    从 Agent 的纯文本输出中解析 AnalysisResult。
    兼容两种情况：
    1. LLM 返回了符合 AnalysisResult 的 JSON → 直接解析
    2. LLM 返回了纯 Markdown 报告 → 包装为 AnalysisResult
    """
    if isinstance(content, AnalysisResult):
        return content

    text = str(content).strip()

    # 尝试从文本中提取 JSON
    json_match = _re.search(r'\{[\s\S]*"final_report"[\s\S]*\}', text)
    if json_match:
        try:
            data = _json.loads(json_match.group())
            return AnalysisResult(**data)
        except Exception:
            pass

    # 纯 Markdown 回退：将整篇报告作为 final_report
    return AnalysisResult(
        query=query,
        paragraphs=[],
        final_report=text,
    )
