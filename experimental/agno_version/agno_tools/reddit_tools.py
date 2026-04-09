# agno_tools/reddit_tools.py
# Reddit 搜索工具
# 申请 OAuth: https://www.reddit.com/prefs/apps
# 创建 "script" 类型应用，拿到 client_id (App ID) + client_secret

import time
from typing import Optional
import requests
from requests.auth import HTTPBasicAuth
from agno.tools import tool

from config import settings

REDDIT_BASE = "https://oauth.reddit.com"
REDDIT_AUTH_URL = "https://www.reddit.com/api/v1/access_token"

# Token 缓存
_token_cache = {"token": None, "expires_at": 0}


def _get_token() -> Optional[str]:
    """获取 OAuth access token，自动缓存"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    client_id = getattr(settings, "REDDIT_CLIENT_ID", None)
    client_secret = getattr(settings, "REDDIT_CLIENT_SECRET", None)
    user_agent = getattr(settings, "REDDIT_USER_AGENT", "agno-mirofish/0.1")

    if not client_id or not client_secret:
        return None

    try:
        r = requests.post(
            REDDIT_AUTH_URL,
            auth=HTTPBasicAuth(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": user_agent},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 3600) - 60
        return _token_cache["token"]
    except Exception as e:
        print(f"⚠️  Reddit OAuth 失败: {e}")
        return None


def _get_headers() -> Optional[dict]:
    token = _get_token()
    if not token:
        return None
    user_agent = getattr(settings, "REDDIT_USER_AGENT", "agno-mirofish/0.1")
    return {
        "Authorization": f"bearer {token}",
        "User-Agent": user_agent,
    }


def _format_post(post: dict, idx: int) -> str:
    data = post.get("data", post)
    title = data.get("title", "(无标题)")
    subreddit = data.get("subreddit", "")
    author = data.get("author", "[deleted]")
    score = data.get("score", 0)
    num_comments = data.get("num_comments", 0)
    created = data.get("created_utc", 0)
    url = "https://reddit.com" + data.get("permalink", "")
    selftext = (data.get("selftext", "") or "")[:400]

    from datetime import datetime
    date_str = datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else ""

    lines = [
        f"{idx}. [{score}↑ {num_comments}💬] r/{subreddit} - {title}",
        f"   作者: u/{author} | 时间: {date_str}",
        f"   URL: {url}",
    ]
    if selftext:
        lines.append(f"   内容: {selftext}")
    return "\n".join(lines)


@tool(description="搜索 Reddit 上的相关帖子，返回 score、评论数、subreddit 等。适用于获取国际社区对某主题的真实讨论")
def search_reddit(query: str, subreddit: Optional[str] = None, max_results: int = 10, sort: str = "relevance") -> str:
    """
    Args:
        query: 搜索关键词
        subreddit: 限定 subreddit（如 "programming"），不填则全站搜
        max_results: 返回结果数
        sort: 'relevance' / 'hot' / 'top' / 'new' / 'comments'
    """
    headers = _get_headers()
    if not headers:
        return "Reddit 工具未配置：请在 .env 中设置 REDDIT_CLIENT_ID 和 REDDIT_CLIENT_SECRET"

    try:
        if subreddit:
            url = f"{REDDIT_BASE}/r/{subreddit}/search"
            params = {"q": query, "limit": max_results, "sort": sort, "restrict_sr": "true"}
        else:
            url = f"{REDDIT_BASE}/search"
            params = {"q": query, "limit": max_results, "sort": sort}

        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        children = data.get("data", {}).get("children", [])
        if not children:
            return f"Reddit 未找到与「{query}」相关的帖子"

        scope = f"r/{subreddit}" if subreddit else "全站"
        lines = [f"Reddit 搜索结果（{scope}，共 {len(children)} 条，按 {sort}）：\n"]
        for i, post in enumerate(children, 1):
            lines.append(_format_post(post, i))
            lines.append("")
        return "\n".join(lines)

    except Exception as e:
        return f"Reddit 搜索失败: {e}"


@tool(description="获取指定 subreddit 的热门帖子，适用于追踪某领域最近的话题热点")
def get_subreddit_hot(subreddit: str, max_results: int = 10, time_filter: str = "week") -> str:
    """
    Args:
        subreddit: subreddit 名称（不带 r/ 前缀，如 "programming"）
        max_results: 返回结果数
        time_filter: 'hour' / 'day' / 'week' / 'month' / 'year' / 'all'
    """
    headers = _get_headers()
    if not headers:
        return "Reddit 工具未配置：请在 .env 中设置 REDDIT_CLIENT_ID 和 REDDIT_CLIENT_SECRET"

    try:
        r = requests.get(
            f"{REDDIT_BASE}/r/{subreddit}/top",
            headers=headers,
            params={"limit": max_results, "t": time_filter},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        children = data.get("data", {}).get("children", [])
        if not children:
            return f"r/{subreddit} 在 {time_filter} 内无热门帖子"

        lines = [f"r/{subreddit} 热门帖子（{time_filter}，共 {len(children)} 条）：\n"]
        for i, post in enumerate(children, 1):
            lines.append(_format_post(post, i))
            lines.append("")
        return "\n".join(lines)

    except Exception as e:
        return f"获取 r/{subreddit} 热门帖子失败: {e}"


@tool(description="获取 Reddit 帖子的热门评论，深度挖掘社区对某话题的真实观点")
def get_reddit_post_comments(post_id: str, subreddit: str, max_results: int = 20) -> str:
    """
    Args:
        post_id: Reddit 帖子 ID（URL 中 /comments/{id}/ 的部分）
        subreddit: 帖子所在的 subreddit
        max_results: 返回评论数
    """
    headers = _get_headers()
    if not headers:
        return "Reddit 工具未配置：请在 .env 中设置 REDDIT_CLIENT_ID 和 REDDIT_CLIENT_SECRET"

    try:
        r = requests.get(
            f"{REDDIT_BASE}/r/{subreddit}/comments/{post_id}",
            headers=headers,
            params={"limit": max_results, "sort": "top"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        if not isinstance(data, list) or len(data) < 2:
            return f"帖子 {post_id} 没有评论"

        comments = data[1].get("data", {}).get("children", [])
        if not comments:
            return f"帖子 {post_id} 评论为空"

        lines = [f"Reddit 帖子评论（共 {len(comments)} 条）：\n"]
        for i, c in enumerate(comments[:max_results], 1):
            cd = c.get("data", {})
            if cd.get("body") in ("[removed]", "[deleted]", None):
                continue
            author = cd.get("author", "[deleted]")
            score = cd.get("score", 0)
            body = cd.get("body", "")[:500]
            lines.append(f"{i}. [{score}↑] u/{author}")
            lines.append(f"   {body}")
            lines.append("")
        return "\n".join(lines)

    except Exception as e:
        return f"获取评论失败: {e}"


def call_reddit_tool(tool_name: str, **kwargs) -> str:
    funcs = {
        "search_reddit": search_reddit,
        "get_subreddit_hot": get_subreddit_hot,
        "get_reddit_post_comments": get_reddit_post_comments,
    }
    if tool_name not in funcs:
        return f"未知 Reddit 工具: {tool_name}"
    fn = funcs[tool_name]
    actual = getattr(fn, "entrypoint", None) or getattr(fn, "fn", None) or fn
    return actual(**kwargs)
