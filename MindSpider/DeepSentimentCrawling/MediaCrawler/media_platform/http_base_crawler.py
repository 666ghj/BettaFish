"""
HTTP-only base crawler for Western platforms.

This base class is for crawlers that only use HTTP APIs
and don't require playwright browser automation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class HTTPBaseCrawler(ABC):
    """
    Abstract base class for HTTP-only crawlers.

    Used for platforms like HackerNews that have public APIs
    and don't require browser automation.
    """

    platform: str = "unknown"

    @abstractmethod
    async def start(self):
        """Initialize the crawler (e.g., create HTTP client)."""
        pass

    @abstractmethod
    async def search(self) -> List[Dict[str, Any]]:
        """
        Search for content.

        Returns:
            List of content dictionaries with standardized fields
        """
        pass

    @abstractmethod
    async def close(self):
        """Clean up resources."""
        pass


class OAuthBaseCrawler(ABC):
    """
    Abstract base class for OAuth-authenticated crawlers.

    Used for platforms like Reddit that use OAuth2 authentication.
    """

    platform: str = "unknown"

    @abstractmethod
    async def start(self):
        """Initialize the crawler and authenticate."""
        pass

    @abstractmethod
    async def search(self) -> List[Dict[str, Any]]:
        """
        Search for content.

        Returns:
            List of content dictionaries with standardized fields
        """
        pass

    @abstractmethod
    async def close(self):
        """Clean up resources."""
        pass


class CookieBaseCrawler(ABC):
    """
    Abstract base class for cookie-authenticated crawlers.

    Used for platforms like Twitter that use cookie-based sessions.
    """

    platform: str = "unknown"

    @abstractmethod
    async def start(self):
        """Initialize the crawler and authenticate via cookies or login."""
        pass

    @abstractmethod
    async def search(self) -> List[Dict[str, Any]]:
        """
        Search for content.

        Returns:
            List of content dictionaries with standardized fields
        """
        pass

    @abstractmethod
    async def close(self):
        """Clean up resources."""
        pass
