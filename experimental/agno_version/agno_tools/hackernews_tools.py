# agno_tools/hackernews_tools.py
# Hacker News 搜索工具，无需任何认证
# 使用 Algolia 的 HN Search API: https://hn.algolia.com/api

from typing import Optional
import requests
from agno.tools import tool

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"


def _format_story(story: dict, idx: int) -> str:
    title = story.get("title") or story.get("story_title") or "(无标题)"
    author = story.get("author", "anon")
    points = story.get("points", 0)
    num_comments = story.get("num_comments", 0)
    url = story.get("url") or f"https://news.ycombinator.com/item?id={story.get('objectID')}"
    created = story.get("created_at", "")[:10]
    text_excerpt = (story.get("story_text") or story.get("comment_text") or "")[:300]

    lines = [
        f"{idx}. [{points}↑ {num_comments}💬] {title}",
        f"   作者: {author} | 时间: {created}",
        f"   URL: {url}",
    ]
    if text_excerpt:
        lines.append(f"   内容: {text_excerpt}")
    return "\n".join(lines)


def _do_hn_search(query: str, tags: str = "story", hits: int = 10, sort: str = "popular") -> str:
    """
    sort: 'popular' (按相关性) 或 'date' (按时间)
    tags: 'story' (主帖) / 'comment' (评论) / 'story,comment'
    """
    endpoint = HN_SEARCH_URL if sort == "popular" else HN_SEARCH_URL + "_by_date"
    try:
        r = requests.get(endpoint, params={"query": query, "tags": tags, "hitsPerPage": hits}, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Hacker News 搜索失败: {e}"

    hits_list = data.get("hits", [])
    if not hits_list:
        return f"Hacker News 未找到与「{query}」相关的内容"

    lines = [f"Hacker News 搜索结果（共 {len(hits_list)} 条，按{'热度' if sort == 'popular' else '时间'}排序）：\n"]
    for i, story in enumerate(hits_list, 1):
        lines.append(_format_story(story, i))
        lines.append("")
    return "\n".join(lines)


@tool(description="搜索 Hacker News 上的相关帖子，返回标题、点数、评论数、链接。适用于获取国际程序员/科技圈对某主题的真实讨论")
def search_hackernews(query: str, max_results: int = 10) -> str:
    """
    Args:
        query: 搜索关键词（建议英文，HN 是英文社区）
        max_results: 返回结果数，默认 10
    """
    return _do_hn_search(query, tags="story", hits=max_results, sort="popular")


@tool(description="搜索 Hacker News 上的最新帖子（按时间排序），适用于追踪最新科技动态")
def search_hackernews_recent(query: str, max_results: int = 10) -> str:
    """
    Args:
        query: 搜索关键词
        max_results: 返回结果数
    """
    return _do_hn_search(query, tags="story", hits=max_results, sort="date")


@tool(description="搜索 Hacker News 上与话题相关的评论，能挖掘到深度讨论和技术细节")
def search_hackernews_comments(query: str, max_results: int = 15) -> str:
    """
    Args:
        query: 搜索关键词
        max_results: 返回评论数
    """
    return _do_hn_search(query, tags="comment", hits=max_results, sort="popular")


# ===== dispatch =====

HN_TOOL_DISPATCH = {
    "search_hackernews": lambda **kw: _do_hn_search(
        kw.get("query", ""), tags="story", hits=kw.get("max_results", 10), sort="popular"),
    "search_hackernews_recent": lambda **kw: _do_hn_search(
        kw.get("query", ""), tags="story", hits=kw.get("max_results", 10), sort="date"),
    "search_hackernews_comments": lambda **kw: _do_hn_search(
        kw.get("query", ""), tags="comment", hits=kw.get("max_results", 15), sort="popular"),
}
