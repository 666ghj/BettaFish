# agno_tools/__init__.py
# 统一导出所有 tool 函数

# QueryAgent 的 6 个 Tavily 新闻搜索工具（已实现）
from .news_search_tools import (
    basic_search_news,
    deep_search_news,
    search_news_last_24_hours,
    search_news_last_week,
    search_images_for_news,
    search_news_by_date,
    call_news_tool,
    NEWS_TOOL_DISPATCH,
)

# MediaAgent 的 5 个 Bocha 多模态搜索工具（已实现）
from .media_search_tools import (
    comprehensive_search,
    web_search_only,
    search_for_structured_data,
    search_last_24_hours,
    search_last_week,
    call_media_tool,
    MEDIA_TOOL_DISPATCH,
)

# InsightAgent 的 6 个本地 DB 查询工具（中文社交媒体）
from .db_query_tools import (
    search_hot_content,
    search_topic_globally,
    search_topic_by_date,
    get_comments_for_topic,
    search_topic_on_platform,
    analyze_sentiment,
    call_insight_tool,
)

# 海外数据源工具（InsightAgent 国际版扩展）
from .hackernews_tools import (
    search_hackernews,
    search_hackernews_recent,
    search_hackernews_comments,
    HN_TOOL_DISPATCH,
)
from .github_tools import (
    search_github_repos,
    search_github_issues,
    search_github_code,
    call_github_tool,
)
from .youtube_tools import (
    search_youtube_videos,
    get_youtube_comments,
    search_youtube_with_comments,
    call_youtube_tool,
)
from .reddit_tools import (
    search_reddit,
    get_subreddit_hot,
    get_reddit_post_comments,
    call_reddit_tool,
)


def call_overseas_tool(tool_name: str, **kwargs) -> str:
    """统一的海外工具调度入口，自动路由到正确的子模块"""
    hn_tools = {"search_hackernews", "search_hackernews_recent", "search_hackernews_comments"}
    github_tools = {"search_github_repos", "search_github_issues", "search_github_code"}
    youtube_tools = {"search_youtube_videos", "get_youtube_comments", "search_youtube_with_comments"}
    reddit_tools = {"search_reddit", "get_subreddit_hot", "get_reddit_post_comments"}

    if tool_name in hn_tools:
        return HN_TOOL_DISPATCH[tool_name](**kwargs)
    elif tool_name in github_tools:
        return call_github_tool(tool_name, **kwargs)
    elif tool_name in youtube_tools:
        return call_youtube_tool(tool_name, **kwargs)
    elif tool_name in reddit_tools:
        return call_reddit_tool(tool_name, **kwargs)
    return f"未知海外工具: {tool_name}"


__all__ = [
    # QueryAgent 工具
    "basic_search_news", "deep_search_news",
    "search_news_last_24_hours", "search_news_last_week",
    "search_images_for_news", "search_news_by_date",
    "call_news_tool", "NEWS_TOOL_DISPATCH",
    # MediaAgent 工具
    "comprehensive_search", "web_search_only",
    "search_for_structured_data",
    "search_last_24_hours", "search_last_week",
    "call_media_tool", "MEDIA_TOOL_DISPATCH",
    # InsightAgent 工具（中文）
    "search_hot_content", "search_topic_globally",
    "search_topic_by_date", "get_comments_for_topic",
    "search_topic_on_platform", "analyze_sentiment",
    "call_insight_tool",
    # 海外数据源（InsightAgent 国际扩展）
    "search_hackernews", "search_hackernews_recent", "search_hackernews_comments",
    "search_github_repos", "search_github_issues", "search_github_code",
    "search_youtube_videos", "get_youtube_comments", "search_youtube_with_comments",
    "search_reddit", "get_subreddit_hot", "get_reddit_post_comments",
    "call_github_tool", "call_youtube_tool", "call_reddit_tool",
    "call_overseas_tool",
]
