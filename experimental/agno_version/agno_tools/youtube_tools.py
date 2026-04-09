# agno_tools/youtube_tools.py
# YouTube Data API v3 工具
# 申请 API Key: https://console.cloud.google.com/apis/library/youtube.googleapis.com
# 免费配额: 10000 units/天 (search 100 units, comments 1 unit)

from typing import Optional
import requests
from agno.tools import tool

from config import settings

YT_BASE = "https://www.googleapis.com/youtube/v3"


def _check_key() -> Optional[str]:
    key = getattr(settings, "YOUTUBE_API_KEY", None)
    if not key:
        return None
    return key


def _format_video(item: dict, idx: int, with_stats: bool = False) -> str:
    snippet = item.get("snippet", {})
    title = snippet.get("title", "(无标题)")
    channel = snippet.get("channelTitle", "")
    published = snippet.get("publishedAt", "")[:10]
    desc = snippet.get("description", "")[:300]
    video_id = item.get("id", {}).get("videoId") if isinstance(item.get("id"), dict) else item.get("id")

    lines = [f"{idx}. {title}"]
    lines.append(f"   频道: {channel} | 发布: {published}")

    if with_stats and "statistics" in item:
        stats = item["statistics"]
        lines.append(
            f"   播放: {stats.get('viewCount', 'N/A')} | "
            f"点赞: {stats.get('likeCount', 'N/A')} | "
            f"评论: {stats.get('commentCount', 'N/A')}"
        )

    if desc:
        lines.append(f"   描述: {desc}")
    lines.append(f"   URL: https://youtube.com/watch?v={video_id}")
    return "\n".join(lines)


@tool(description="搜索 YouTube 上的视频，返回标题、频道、发布时间、描述。适用于发现海外视频内容对某主题的讨论")
def search_youtube_videos(query: str, max_results: int = 10) -> str:
    """
    Args:
        query: 搜索关键词
        max_results: 返回结果数，默认 10
    """
    api_key = _check_key()
    if not api_key:
        return "YouTube 工具未配置：请在 .env 中设置 YOUTUBE_API_KEY"

    try:
        # 第一步：search 拿 video IDs
        search_resp = requests.get(
            f"{YT_BASE}/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "key": api_key,
                "relevanceLanguage": "en",
                "order": "relevance",
            },
            timeout=30,
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
        items = search_data.get("items", [])

        if not items:
            return f"YouTube 未找到与「{query}」相关的视频"

        # 第二步：批量获取统计数据
        video_ids = [it["id"]["videoId"] for it in items if "videoId" in it.get("id", {})]
        stats_resp = requests.get(
            f"{YT_BASE}/videos",
            params={
                "part": "statistics,snippet",
                "id": ",".join(video_ids),
                "key": api_key,
            },
            timeout=30,
        )
        stats_resp.raise_for_status()
        videos = stats_resp.json().get("items", [])

        lines = [f"YouTube 搜索结果（共 {len(videos)} 个）：\n"]
        for i, video in enumerate(videos, 1):
            lines.append(_format_video(video, i, with_stats=True))
            lines.append("")
        return "\n".join(lines)

    except Exception as e:
        return f"YouTube 搜索失败: {e}"


@tool(description="获取 YouTube 视频的热门评论，能挖掘海外观众对视频内容的真实反馈和情感")
def get_youtube_comments(video_id: str, max_results: int = 20) -> str:
    """
    Args:
        video_id: YouTube 视频 ID（URL 中 v= 后面的部分）
        max_results: 返回评论数，默认 20
    """
    api_key = _check_key()
    if not api_key:
        return "YouTube 工具未配置：请在 .env 中设置 YOUTUBE_API_KEY"

    try:
        r = requests.get(
            f"{YT_BASE}/commentThreads",
            params={
                "part": "snippet",
                "videoId": video_id,
                "maxResults": max_results,
                "order": "relevance",
                "key": api_key,
                "textFormat": "plainText",
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])

        if not items:
            return f"视频 {video_id} 没有评论或评论已禁用"

        lines = [f"YouTube 评论（视频 {video_id}，共 {len(items)} 条）：\n"]
        for i, item in enumerate(items, 1):
            top = item["snippet"]["topLevelComment"]["snippet"]
            author = top.get("authorDisplayName", "")
            text = top.get("textDisplay", "")[:500]
            likes = top.get("likeCount", 0)
            published = top.get("publishedAt", "")[:10]
            lines.append(f"{i}. [{likes}👍] {author} ({published})")
            lines.append(f"   {text}")
            lines.append("")
        return "\n".join(lines)

    except Exception as e:
        return f"YouTube 评论获取失败: {e}"


@tool(description="搜索 YouTube 视频并直接拉取热门视频的评论汇总，一步到位获取多模态社区反馈")
def search_youtube_with_comments(query: str, max_videos: int = 3, comments_per_video: int = 10) -> str:
    """
    Args:
        query: 搜索关键词
        max_videos: 取多少个视频（默认 3）
        comments_per_video: 每个视频取多少条评论
    """
    videos_text = search_youtube_videos.entrypoint(query=query, max_results=max_videos) \
        if hasattr(search_youtube_videos, "entrypoint") \
        else search_youtube_videos(query=query, max_results=max_videos)

    if "未找到" in videos_text or "失败" in videos_text or "未配置" in videos_text:
        return videos_text

    # 提取 video IDs
    import re
    video_ids = re.findall(r"watch\?v=([\w-]+)", videos_text)

    parts = [videos_text, "\n===== 各视频评论 =====\n"]
    for vid in video_ids[:max_videos]:
        get_fn = get_youtube_comments.entrypoint if hasattr(get_youtube_comments, "entrypoint") else get_youtube_comments
        parts.append(get_fn(video_id=vid, max_results=comments_per_video))
        parts.append("")
    return "\n".join(parts)


def call_youtube_tool(tool_name: str, **kwargs) -> str:
    funcs = {
        "search_youtube_videos": search_youtube_videos,
        "get_youtube_comments": get_youtube_comments,
        "search_youtube_with_comments": search_youtube_with_comments,
    }
    if tool_name not in funcs:
        return f"未知 YouTube 工具: {tool_name}"
    fn = funcs[tool_name]
    actual = getattr(fn, "entrypoint", None) or getattr(fn, "fn", None) or fn
    return actual(**kwargs)
