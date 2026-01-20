"""
HackerNews crawler module using Algolia Search API and Firebase API.

Supports:
- Search stories by keyword
- Fetch story details
- Get comments
- Top/New/Best story lists
- No authentication required (public API)
"""


def __getattr__(name):
    """Lazy import to avoid playwright dependency for client-only usage."""
    if name == "HackerNewsCrawler":
        from .core import HackerNewsCrawler
        return HackerNewsCrawler
    elif name == "HackerNewsClient":
        from .client import HackerNewsClient
        return HackerNewsClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["HackerNewsCrawler", "HackerNewsClient"]
