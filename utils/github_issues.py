"""
GitHub Issues 工具模块

提供创建 GitHub Issues URL 和显示带链接的错误信息的功能
数据模型定义位置：
- 无数据模型
"""

from datetime import datetime
from urllib.parse import quote

# GitHub 仓库信息
GITHUB_REPO = "666ghj/BettaFish"
GITHUB_ISSUES_URL = f"https://github.com/{GITHUB_REPO}/issues/new"


def create_issue_url(title: str, body: str = "") -> str:
    """
    创建 GitHub Issues URL，预填充标题和内容
    
    Args:
        title: Issue 标题
        body: Issue 内容（可选）
    
    Returns:
        完整的 GitHub Issues URL
    """
    encoded_title = quote(title)
    encoded_body = quote(body) if body else ""
    
    if encoded_body:
        return f"{GITHUB_ISSUES_URL}?title={encoded_title}&body={encoded_body}"
    else:
        return f"{GITHUB_ISSUES_URL}?title={encoded_title}"


def error_with_issue_link(
    error_message: str,
    error_details: str = "",
    app_name: str = "Streamlit App"
) -> str:
    """
    生成带 GitHub Issues 链接的错误信息字符串
    
    仅在通用异常处理中使用，不用于用户配置错误
    
    Args:
        error_message: 错误消息
        error_details: 错误详情（可选，用于填充到 Issue body）
        app_name: 应用名称，用于标识错误来源
    
    Returns:
        包含错误信息和 GitHub Issues 链接的 Markdown 格式字符串
    """
    issue_title = f"[{app_name}] {error_message[:50]}"
    issue_body = f"## 错误信息\n\n{error_message}\n\n"
    
    if error_details:
        issue_body += f"## 错误详情\n\n```\n{error_details}\n```\n\n"
    
    issue_body += f"## 环境信息\n\n- 应用: {app_name}\n- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    issue_url = create_issue_url(issue_title, issue_body)
    
    # 使用 markdown 格式添加超链接
    error_display = f"{error_message}\n\n[📝 提交错误报告]({issue_url})"
    
    if error_details:
        error_display = f"{error_message}\n\n```\n{error_details}\n```\n\n[📝 提交错误报告]({issue_url})"
    
    return error_display


__all__ = [
    "create_issue_url",
    "error_with_issue_link",
    "GITHUB_REPO",
    "GITHUB_ISSUES_URL",
]

