"""
Twitter/X crawler module using twikit library.

Supports:
- Search tweets by keyword
- Fetch tweet details
- Get comments/replies
- User profile information
- Cookie-based authentication
"""


def __getattr__(name):
    """Lazy import to avoid playwright dependency for client-only usage."""
    if name == "TwitterCrawler":
        from .core import TwitterCrawler
        return TwitterCrawler
    elif name == "TwitterClient":
        from .client import TwitterClient
        return TwitterClient
    elif name == "TwitterLoginManager":
        from .login import TwitterLoginManager
        return TwitterLoginManager
    elif name == "create_authenticated_client":
        from .login import create_authenticated_client
        return create_authenticated_client
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TwitterCrawler",
    "TwitterClient",
    "TwitterLoginManager",
    "create_authenticated_client",
]
