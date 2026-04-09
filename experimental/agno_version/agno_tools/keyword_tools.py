# agno_tools/keyword_tools.py
# TODO(A组): 迁移自 InsightEngine/tools/keyword_optimizer.py
# 注意：此工具内部调用 LLM，但对外只是普通 tool 函数，不引入 agno Agent

from agno.tools import tool
from typing import List


@tool(description="将用户查询优化扩展为多个数据库搜索关键词，提高搜索覆盖率")
def optimize_keywords(query: str, num_keywords: int = 5) -> List[str]:
    """
    Args:
        query: 用户原始查询，如 "特斯拉召回事件"
        num_keywords: 需要生成的关键词数量，默认5个
    Returns:
        优化后的关键词列表，如 ["特斯拉召回", "Model 3刹车", "特斯拉质量问题", ...]
    """
    raise NotImplementedError("TODO(A组): 迁移自 InsightEngine/tools/keyword_optimizer.py")
