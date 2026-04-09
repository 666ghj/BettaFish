# agno_tools/news_search_tools.py
# 迁移自 BettaFish/QueryEngine/tools/search.py
# 6 个基于 Tavily API 的新闻搜索工具，供 QueryAgent 使用

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from agno.tools import tool
from tavily import TavilyClient

from config import settings


@dataclass
class SearchResult:
    title: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
    score: Optional[float] = None
    published_date: Optional[str] = None


@dataclass
class ImageResult:
    url: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TavilyResponse:
    query: Optional[str] = None
    answer: Optional[str] = None
    results: List[SearchResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    response_time: Optional[float] = None


_client: Optional[TavilyClient] = None


def _get_client() -> TavilyClient:
    """懒加载全局 Tavily 客户端"""
    global _client
    if _client is None:
        api_key = settings.TAVILY_API_KEY
        if not api_key:
            raise ValueError("TAVILY_API_KEY 未在 .env 中配置")
        _client = TavilyClient(api_key=api_key)
    return _client


def _do_search(**kwargs) -> TavilyResponse:
    """内部统一执行函数"""
    try:
        client = _get_client()
        kwargs.setdefault("topic", "general")
        api_params = {k: v for k, v in kwargs.items() if v is not None}
        resp = client.search(**api_params)

        return TavilyResponse(
            query=resp.get("query"),
            answer=resp.get("answer"),
            results=[
                SearchResult(
                    title=item.get("title"),
                    url=item.get("url"),
                    content=item.get("content"),
                    score=item.get("score"),
                    published_date=item.get("published_date"),
                )
                for item in resp.get("results", [])
            ],
            images=[
                ImageResult(url=item.get("url"), description=item.get("description"))
                for item in resp.get("images", [])
            ],
            response_time=resp.get("response_time"),
        )
    except Exception as e:
        return TavilyResponse(query=kwargs.get("query"), answer=f"搜索失败: {e}")


def _format_response(resp: TavilyResponse) -> str:
    """将 TavilyResponse 格式化为 LLM 可消费的字符串"""
    lines = [f"搜索查询: {resp.query}"]
    if resp.answer:
        lines.append(f"\nAI 摘要: {resp.answer}")
    if resp.results:
        lines.append(f"\n搜索结果（{len(resp.results)} 条）：")
        for i, r in enumerate(resp.results, 1):
            date = f" [{r.published_date}]" if r.published_date else ""
            lines.append(f"\n{i}. {r.title}{date}")
            lines.append(f"   URL: {r.url}")
            if r.content:
                lines.append(f"   内容: {r.content[:500]}")
    if resp.images:
        lines.append(f"\n相关图片（{len(resp.images)} 张）：")
        for i, img in enumerate(resp.images, 1):
            desc = f" - {img.description}" if img.description else ""
            lines.append(f"{i}. {img.url}{desc}")
    return "\n".join(lines)


# ===== 6 个 Agent 工具 =====

@tool(description="基础新闻搜索：标准、快速的通用新闻搜索，适用于不确定需要何种特定搜索时")
def basic_search_news(query: str, max_results: int = 7) -> str:
    """
    Args:
        query: 搜索查询词
        max_results: 最大结果数，默认 7
    """
    resp = _do_search(query=query, max_results=max_results, search_depth="basic", include_answer=False)
    return _format_response(resp)


@tool(description="深度新闻分析：对一个主题进行最全面、最深入的搜索，返回 AI 高级摘要和最多20条最相关的新闻")
def deep_search_news(query: str) -> str:
    """
    Args:
        query: 搜索查询词
    """
    resp = _do_search(query=query, search_depth="advanced", max_results=20, include_answer="advanced")
    return _format_response(resp)


@tool(description="搜索过去24小时内发布的最新新闻，适用于追踪突发事件或最新进展")
def search_news_last_24_hours(query: str) -> str:
    """
    Args:
        query: 搜索查询词
    """
    resp = _do_search(query=query, time_range="d", max_results=10)
    return _format_response(resp)


@tool(description="搜索过去一周内发布的新闻报道，适用于周度舆情总结或回顾")
def search_news_last_week(query: str) -> str:
    """
    Args:
        query: 搜索查询词
    """
    resp = _do_search(query=query, time_range="w", max_results=10)
    return _format_response(resp)


@tool(description="查找与新闻主题相关的图片，返回图片链接及描述，适用于为报告配图")
def search_images_for_news(query: str) -> str:
    """
    Args:
        query: 搜索查询词
    """
    resp = _do_search(
        query=query,
        include_images=True,
        include_image_descriptions=True,
        max_results=5,
    )
    return _format_response(resp)


@tool(description="按指定日期范围搜索新闻，适用于对特定历史时段的事件进行分析")
def search_news_by_date(query: str, start_date: str, end_date: str) -> str:
    """
    Args:
        query: 搜索查询词
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
    """
    resp = _do_search(query=query, start_date=start_date, end_date=end_date, max_results=15)
    return _format_response(resp)


# ===== 给 run_single_agent.py 用的纯函数版本（不带 @tool 装饰器）=====
# 因为 @tool 装饰后不能直接当普通函数调用，这里提供一个 dispatch 字典

NEWS_TOOL_DISPATCH = {
    "basic_search_news": lambda **kw: _format_response(_do_search(
        query=kw["query"], max_results=kw.get("max_results", 7),
        search_depth="basic", include_answer=False)),
    "deep_search_news": lambda **kw: _format_response(_do_search(
        query=kw["query"], search_depth="advanced", max_results=20, include_answer="advanced")),
    "search_news_last_24_hours": lambda **kw: _format_response(_do_search(
        query=kw["query"], time_range="d", max_results=10)),
    "search_news_last_week": lambda **kw: _format_response(_do_search(
        query=kw["query"], time_range="w", max_results=10)),
    "search_images_for_news": lambda **kw: _format_response(_do_search(
        query=kw["query"], include_images=True, include_image_descriptions=True, max_results=5)),
    "search_news_by_date": lambda **kw: _format_response(_do_search(
        query=kw["query"], start_date=kw["start_date"], end_date=kw["end_date"], max_results=15)),
}


def call_news_tool(tool_name: str, **kwargs) -> str:
    """根据工具名调度调用，供 run_single_agent.py 在多步流程中使用"""
    if tool_name not in NEWS_TOOL_DISPATCH:
        return f"未知工具: {tool_name}"
    try:
        return NEWS_TOOL_DISPATCH[tool_name](**kwargs)
    except Exception as e:
        return f"工具 {tool_name} 调用失败: {e}"
