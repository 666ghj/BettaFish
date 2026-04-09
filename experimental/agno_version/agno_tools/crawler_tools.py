# agno_tools/crawler_tools.py
# TODO(A组): 迁移自 MindSpider/main.py
# 将 MindSpider 类的启动和状态查询封装为 agno @tool 函数

from agno.tools import tool
from typing import List, Dict, Any


@tool(description="启动MindSpider爬虫，采集指定平台的舆情数据并存入数据库")
def start_crawler(
    keyword: str,
    platforms: List[str],
    max_count: int = 100
) -> Dict[str, Any]:
    """
    Args:
        keyword: 采集关键词
        platforms: 目标平台列表，如 ["weibo", "tieba", "zhihu"]
        max_count: 每个平台最大采集条数
    Returns:
        {"task_id": str, "status": "started", "estimated_seconds": int}
    """
    raise NotImplementedError("TODO(A组): 迁移自 MindSpider/main.py MindSpider类")


@tool(description="查询爬虫任务当前状态和进度")
def get_crawler_status(task_id: str) -> Dict[str, Any]:
    """
    Args:
        task_id: start_crawler 返回的任务ID
    Returns:
        {"task_id": str, "status": "running|done|failed", "progress": int, "collected": int}
    """
    raise NotImplementedError("TODO(A组): 迁移自 MindSpider/main.py MindSpider类")
