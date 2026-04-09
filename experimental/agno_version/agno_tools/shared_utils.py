# agno_tools/shared_utils.py
# TODO(A组): 迁移自各 Engine 的 utils/ 目录
# 公共工具函数，供所有 tool 和 agent 使用

from typing import List, Dict, Any


def format_search_results(results: List[Dict[str, Any]], max_length: int = 500) -> str:
    """
    将搜索结果列表格式化为供 LLM 阅读的字符串。
    迁移自 InsightEngine/utils/text_processing.py 的 format_search_results_for_prompt

    Args:
        results: search_* tool 返回的数据列表
        max_length: 每条结果内容的最大字符数
    Returns:
        格式化后的多行字符串
    """
    raise NotImplementedError("TODO(A组): 迁移自 InsightEngine/utils/")
