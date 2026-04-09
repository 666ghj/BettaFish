# agno_agents/__init__.py
# 统一导出三个核心 Agent 的工厂函数、运行接口和共享模型

from .models import (
    SearchDecision,
    ParagraphOutline,
    ReportStructure,
    ParagraphResult,
    AnalysisResult,
)
from .insight_agent import create_insight_agent, run_insight_analysis
from .media_agent import create_media_agent, run_media_analysis
from .query_agent import create_query_agent, run_query
from .report_agent import (
    ReportAgent,
    create_report_agent,
    run_report_generation,
    run_report_generation_async,
)

__all__ = [
    # 共享模型（ForumEngine / ReportEngine 消费）
    "SearchDecision", "ParagraphOutline", "ReportStructure",
    "ParagraphResult", "AnalysisResult",
    # 三个核心 Agent
    "create_insight_agent", "run_insight_analysis",
    "create_media_agent", "run_media_analysis",
    "create_query_agent", "run_query",
    # ReportAgent
    "ReportAgent", "create_report_agent",
    "run_report_generation", "run_report_generation_async",
]
