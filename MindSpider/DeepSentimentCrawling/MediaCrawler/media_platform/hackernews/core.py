"""
HackerNews crawler using Algolia Search API and Firebase API.

Features:
- No authentication required (public APIs)
- Search via Algolia (fast, full-text search)
- Item details via Firebase API
- No rate limiting issues (generous limits)
- No Cloudflare protection
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
import httpx

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import HTTP-only base class (no playwright dependency)
from ..http_base_crawler import HTTPBaseCrawler

# Import config
try:
    from config import settings
except ImportError:
    settings = None


class HackerNewsCrawler(HTTPBaseCrawler):
    """
    HackerNews crawler using public Algolia and Firebase APIs.

    No authentication required. Very permissive rate limits.
    """

    platform = "hackernews"

    # API endpoints
    ALGOLIA_URL = "https://hn.algolia.com/api/v1"
    FIREBASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self):
        self.client = None
        self.keyword = ""
        self.max_results = 50
        self.search_type = "story"  # story, comment, poll, job, show_hn, ask_hn

        # Load config
        if settings:
            self.max_results = min(settings.HACKERNEWS_MAX_RESULTS, 1000)

    async def start(self):
        """
        Initialize HTTP client.

        No authentication needed for HackerNews.
        """
        logger.info("Starting HackerNews crawler...")
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "BettaFish/1.0 (Public Opinion Analysis)"
            }
        )
        logger.info("HackerNews: Client initialized (no auth required)")

    async def search(self) -> List[Dict[str, Any]]:
        """
        Search HackerNews stories via Algolia API.

        Returns:
            List of story dictionaries with standardized fields
        """
        if not self.client:
            await self.start()

        if not self.keyword:
            logger.error("HackerNews: No keyword set for search")
            return []

        results = []
        logger.info(f"HackerNews: Searching for '{self.keyword}'...")

        try:
            # Build search URL with filters
            tags = f"({self.search_type})"
            url = f"{self.ALGOLIA_URL}/search"

            response = await self.client.get(
                url,
                params={
                    "query": self.keyword,
                    "tags": tags,
                    "hitsPerPage": min(self.max_results, 1000),
                }
            )
            response.raise_for_status()
            data = response.json()

            for hit in data.get("hits", []):
                result = self._parse_algolia_hit(hit)
                if result:
                    results.append(result)

            logger.info(f"HackerNews: Found {len(results)} items")

        except httpx.HTTPStatusError as e:
            logger.error(f"HackerNews: HTTP error {e.response.status_code}")
        except Exception as e:
            logger.error(f"HackerNews: Search error: {e}")

        return results

    def _parse_algolia_hit(self, hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Algolia search result into standardized dictionary."""
        try:
            return {
                "id": hit.get("objectID"),
                "platform": self.platform,
                "title": hit.get("title", ""),
                "content": hit.get("story_text") or hit.get("comment_text") or "",
                "url": hit.get("url", ""),
                "author": hit.get("author", ""),
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "story_id": hit.get("story_id"),
                "parent_id": hit.get("parent_id"),
                "created_at": hit.get("created_at"),
                "created_at_i": hit.get("created_at_i"),  # Unix timestamp
                "item_type": hit.get("_tags", ["story"])[0] if hit.get("_tags") else "story",
                "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "collected_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"HackerNews: Failed to parse hit: {e}")
            return None

    async def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get item details from Firebase API.

        Args:
            item_id: HackerNews item ID

        Returns:
            Item dictionary or None
        """
        if not self.client:
            await self.start()

        try:
            url = f"{self.FIREBASE_URL}/item/{item_id}.json"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data:
                return self._parse_firebase_item(data)
        except Exception as e:
            logger.error(f"HackerNews: Failed to get item {item_id}: {e}")

        return None

    def _parse_firebase_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Firebase item into standardized dictionary."""
        return {
            "id": str(item.get("id")),
            "platform": self.platform,
            "title": item.get("title", ""),
            "content": item.get("text", ""),
            "url": item.get("url", ""),
            "author": item.get("by", ""),
            "points": item.get("score", 0),
            "num_comments": len(item.get("kids", [])),
            "parent_id": str(item.get("parent")) if item.get("parent") else None,
            "item_type": item.get("type", "story"),
            "dead": item.get("dead", False),
            "deleted": item.get("deleted", False),
            "created_at_i": item.get("time"),
            "created_at": datetime.fromtimestamp(item.get("time", 0)).isoformat() if item.get("time") else None,
            "hn_url": f"https://news.ycombinator.com/item?id={item.get('id')}",
            "kids": item.get("kids", []),  # Comment IDs
            "collected_at": datetime.now().isoformat(),
        }

    async def get_comments(self, story_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get comments for a story.

        Args:
            story_id: HackerNews story ID
            limit: Maximum comments to fetch

        Returns:
            List of comment dictionaries
        """
        if not self.client:
            await self.start()

        comments = []

        try:
            # Get story to find comment IDs
            story = await self.get_item(story_id)
            if not story or not story.get("kids"):
                return comments

            # Fetch comments (limited)
            comment_ids = story["kids"][:limit]

            for comment_id in comment_ids:
                comment = await self.get_item(str(comment_id))
                if comment and not comment.get("deleted") and not comment.get("dead"):
                    comment["story_id"] = story_id
                    comments.append(comment)

        except Exception as e:
            logger.error(f"HackerNews: Failed to get comments for {story_id}: {e}")

        return comments

    async def get_top_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get current top stories from HackerNews.

        Args:
            limit: Maximum stories to fetch

        Returns:
            List of story dictionaries
        """
        if not self.client:
            await self.start()

        stories = []

        try:
            # Get top story IDs
            url = f"{self.FIREBASE_URL}/topstories.json"
            response = await self.client.get(url)
            response.raise_for_status()
            story_ids = response.json()[:limit]

            # Fetch each story
            for story_id in story_ids:
                story = await self.get_item(str(story_id))
                if story:
                    stories.append(story)

        except Exception as e:
            logger.error(f"HackerNews: Failed to get top stories: {e}")

        return stories

    async def search_by_date(
        self,
        keyword: str = None,
        start_date: int = None,
        end_date: int = None
    ) -> List[Dict[str, Any]]:
        """
        Search HackerNews with date filters.

        Args:
            keyword: Search query (optional)
            start_date: Unix timestamp for start
            end_date: Unix timestamp for end

        Returns:
            List of item dictionaries
        """
        if not self.client:
            await self.start()

        results = []
        query = keyword or self.keyword

        try:
            url = f"{self.ALGOLIA_URL}/search_by_date"
            params = {
                "tags": f"({self.search_type})",
                "hitsPerPage": min(self.max_results, 1000),
            }

            if query:
                params["query"] = query

            # Add date filters if provided
            filters = []
            if start_date:
                filters.append(f"created_at_i>={start_date}")
            if end_date:
                filters.append(f"created_at_i<={end_date}")
            if filters:
                params["numericFilters"] = ",".join(filters)

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for hit in data.get("hits", []):
                result = self._parse_algolia_hit(hit)
                if result:
                    results.append(result)

        except Exception as e:
            logger.error(f"HackerNews: Date search error: {e}")

        return results

    async def close(self):
        """Clean up resources."""
        if self.client:
            await self.client.aclose()
        logger.info("HackerNews crawler closed")
