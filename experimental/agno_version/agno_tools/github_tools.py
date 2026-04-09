# agno_tools/github_tools.py
# GitHub 搜索工具，可选 GITHUB_TOKEN（无 token 60 req/h，有 token 5000 req/h）

from typing import Optional
import requests
from agno.tools import tool

from config import settings

GITHUB_BASE = "https://api.github.com"


def _get_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = getattr(settings, "GITHUB_TOKEN", None)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _do_github_search(endpoint: str, query: str, sort: str = "best-match", per_page: int = 10) -> dict:
    try:
        params = {"q": query, "per_page": per_page}
        if sort != "best-match":
            params["sort"] = sort
        r = requests.get(f"{GITHUB_BASE}/search/{endpoint}", headers=_get_headers(), params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}


@tool(description="搜索 GitHub 上的开源仓库，返回 star 数、描述、语言等。适用于了解某技术工具的开源生态")
def search_github_repos(query: str, max_results: int = 10) -> str:
    """
    Args:
        query: 搜索关键词，可用 GitHub 搜索语法（如 "claude code language:python stars:>100"）
        max_results: 返回结果数
    """
    data = _do_github_search("repositories", query, sort="stars", per_page=max_results)
    if "_error" in data:
        return f"GitHub 仓库搜索失败: {data['_error']}"

    items = data.get("items", [])
    if not items:
        return f"GitHub 未找到与「{query}」相关的仓库"

    lines = [f"GitHub 仓库搜索结果（共 {len(items)} 个，按 star 排序）：\n"]
    for i, repo in enumerate(items, 1):
        lines.append(f"{i}. ⭐ {repo.get('stargazers_count', 0)} | 🍴 {repo.get('forks_count', 0)} | {repo.get('full_name')}")
        lines.append(f"   语言: {repo.get('language', 'N/A')} | 更新: {repo.get('updated_at', '')[:10]}")
        if repo.get("description"):
            lines.append(f"   描述: {repo['description'][:200]}")
        lines.append(f"   URL: {repo.get('html_url')}")
        lines.append("")
    return "\n".join(lines)


@tool(description="搜索 GitHub 上的 issues 和 discussions，能挖掘开发者对某工具/库的反馈、bug 报告和功能讨论")
def search_github_issues(query: str, max_results: int = 10) -> str:
    """
    Args:
        query: 搜索关键词，可用 GitHub 搜索语法（如 "claude code is:issue label:bug"）
        max_results: 返回结果数
    """
    data = _do_github_search("issues", query, sort="updated", per_page=max_results)
    if "_error" in data:
        return f"GitHub Issues 搜索失败: {data['_error']}"

    items = data.get("items", [])
    if not items:
        return f"GitHub 未找到与「{query}」相关的 issue/discussion"

    lines = [f"GitHub Issues/Discussions 搜索结果（共 {len(items)} 条）：\n"]
    for i, issue in enumerate(items, 1):
        state = issue.get("state", "?")
        emoji = "🟢" if state == "open" else "🔴"
        repo_url = issue.get("repository_url", "").replace("https://api.github.com/repos/", "")
        lines.append(f"{i}. {emoji} [{state}] {issue.get('title')}")
        lines.append(f"   仓库: {repo_url} | 评论: {issue.get('comments', 0)} | 创建: {issue.get('created_at', '')[:10]}")
        if issue.get("body"):
            lines.append(f"   内容: {issue['body'][:300]}")
        lines.append(f"   URL: {issue.get('html_url')}")
        lines.append("")
    return "\n".join(lines)


@tool(description="搜索 GitHub 上的代码片段，能找到具体的实现示例和使用方式")
def search_github_code(query: str, max_results: int = 5) -> str:
    """
    Args:
        query: 搜索关键词
        max_results: 返回结果数（代码搜索建议较少）
    """
    data = _do_github_search("code", query, per_page=max_results)
    if "_error" in data:
        return f"GitHub 代码搜索失败: {data['_error']}"

    items = data.get("items", [])
    if not items:
        return f"GitHub 未找到与「{query}」相关的代码"

    lines = [f"GitHub 代码搜索结果（共 {len(items)} 条）：\n"]
    for i, code in enumerate(items, 1):
        lines.append(f"{i}. {code.get('name')} in {code.get('repository', {}).get('full_name')}")
        lines.append(f"   路径: {code.get('path')}")
        lines.append(f"   URL: {code.get('html_url')}")
        lines.append("")
    return "\n".join(lines)


# ===== dispatch =====

GITHUB_TOOL_DISPATCH = {
    "search_github_repos": lambda **kw: search_github_repos.entrypoint(query=kw.get("query", ""), max_results=kw.get("max_results", 10))
        if hasattr(search_github_repos, "entrypoint") else None,
}


def call_github_tool(tool_name: str, **kwargs) -> str:
    funcs = {
        "search_github_repos": search_github_repos,
        "search_github_issues": search_github_issues,
        "search_github_code": search_github_code,
    }
    if tool_name not in funcs:
        return f"未知 GitHub 工具: {tool_name}"
    fn = funcs[tool_name]
    actual = getattr(fn, "entrypoint", None) or getattr(fn, "fn", None) or fn
    return actual(**kwargs)
