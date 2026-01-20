"""
Reddit crawler module using PRAW (Python Reddit API Wrapper).

Supports:
- Search posts by keyword
- Subreddit browsing
- Comment fetching
- User submissions
- OAuth-based authentication
"""


def __getattr__(name):
    """Lazy import to avoid playwright dependency for client-only usage."""
    if name == "RedditCrawler":
        from .core import RedditCrawler
        return RedditCrawler
    elif name == "RedditClient":
        from .client import RedditClient
        return RedditClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["RedditCrawler", "RedditClient"]
