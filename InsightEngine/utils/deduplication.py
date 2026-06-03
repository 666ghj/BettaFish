"""
Search-result deduplication helpers.
"""

from typing import Any, Tuple


def build_result_dedup_key(result: Any) -> Tuple[Any, ...]:
    """
    Build a stable deduplication key for a search result.

    URL-backed results keep the historical URL-only behavior. Results without a
    URL need the full content and source metadata so distinct comments or posts
    are not collapsed just because they share a long prefix.
    """
    url = getattr(result, "url", None)
    if url:
        return ("url", url)

    publish_time = getattr(result, "publish_time", None)
    if publish_time is not None and hasattr(publish_time, "isoformat"):
        publish_time = publish_time.isoformat()

    return (
        "content",
        getattr(result, "platform", None),
        getattr(result, "content_type", None),
        getattr(result, "source_table", None),
        getattr(result, "author_nickname", None),
        publish_time,
        getattr(result, "title_or_content", "") or "",
    )
