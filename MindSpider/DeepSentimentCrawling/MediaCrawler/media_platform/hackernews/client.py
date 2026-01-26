# -*- coding: utf-8 -*-
"""
HackerNews API client using Algolia Search API and Firebase API.

Provides access to HackerNews stories, comments, and users without authentication.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

try:
    from config import settings
except ImportError:
    settings = None


class HackerNewsClient:
    """
    HackerNews API client using public APIs.

    Uses:
    - Algolia Search API for full-text search
    - Firebase API for item/user details

    No authentication required.
    """

    # API endpoints
    ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
    FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"

    def __init__(
        self,
        timeout: float = 30.0,
        rate_limit_delay: float = 0.5,
    ):
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx not installed. Install with: pip install httpx"
            )

        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay

        # Load config defaults
        if settings:
            self.rate_limit_delay = getattr(
                settings, 'WESTERN_CRAWLER_RATE_LIMIT_DELAY',
                self.rate_limit_delay
            )

        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        await asyncio.sleep(self.rate_limit_delay)

    async def search(
        self,
        query: str,
        tags: Optional[str] = None,
        sort_by: str = "relevance",
        page: int = 0,
        hits_per_page: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search HackerNews using Algolia.

        Args:
            query: Search query string
            tags: Filter by tags (story, comment, poll, ask_hn, show_hn, etc.)
            sort_by: 'relevance' or 'date'
            page: Page number (0-indexed)
            hits_per_page: Results per page (max 1000)

        Returns:
            List of search result dictionaries
        """
        client = await self._get_client()
        await self._rate_limit()

        endpoint = "search" if sort_by == "relevance" else "search_by_date"
        url = f"{self.ALGOLIA_BASE}/{endpoint}"

        params = {
            "query": query,
            "page": page,
            "hitsPerPage": min(hits_per_page, 1000),
        }
        if tags:
            params["tags"] = tags

        results = []
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for hit in data.get("hits", []):
                parsed = self._parse_algolia_hit(hit)
                if parsed:
                    results.append(parsed)

            logger.info(f"HackerNews: Found {len(results)} results for '{query}'")

        except Exception as e:
            logger.error(f"HackerNews: Search error: {e}")

        return results

    async def search_stories(
        self,
        query: str,
        sort_by: str = "relevance",
        page: int = 0,
        hits_per_page: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search only stories (not comments)."""
        return await self.search(
            query=query,
            tags="story",
            sort_by=sort_by,
            page=page,
            hits_per_page=hits_per_page,
        )

    async def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get item details from Firebase API.

        Args:
            item_id: HackerNews item ID

        Returns:
            Item dictionary or None
        """
        client = await self._get_client()
        await self._rate_limit()

        url = f"{self.FIREBASE_BASE}/item/{item_id}.json"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if data:
                return self._parse_firebase_item(data)

        except Exception as e:
            logger.error(f"HackerNews: Failed to get item {item_id}: {e}")

        return None

    async def get_items(self, item_ids: List[int]) -> List[Dict[str, Any]]:
        """Get multiple items concurrently."""
        tasks = [self.get_item(item_id) for item_id in item_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    async def get_story_comments(
        self,
        story_id: int,
        max_depth: int = 3,
        max_comments: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get comments for a story.

        Args:
            story_id: Story item ID
            max_depth: Maximum comment thread depth
            max_comments: Maximum comments to fetch

        Returns:
            List of comment dictionaries
        """
        story = await self.get_item(story_id)
        if not story:
            return []

        kid_ids = story.get("kids", [])
        if not kid_ids:
            return []

        comments = []
        await self._fetch_comments_recursive(
            kid_ids[:max_comments],
            comments,
            story_id,
            0,
            max_depth,
            max_comments,
        )

        return comments[:max_comments]

    async def _fetch_comments_recursive(
        self,
        item_ids: List[int],
        results: List[Dict],
        story_id: int,
        depth: int,
        max_depth: int,
        max_comments: int,
    ):
        """Recursively fetch comment tree."""
        if depth > max_depth or len(results) >= max_comments:
            return

        for item_id in item_ids:
            if len(results) >= max_comments:
                break

            item = await self.get_item(item_id)
            if item and item.get("type") == "comment":
                item["story_id"] = story_id
                item["depth"] = depth
                results.append(item)

                # Fetch child comments
                kids = item.get("kids", [])
                if kids and depth < max_depth:
                    await self._fetch_comments_recursive(
                        kids,
                        results,
                        story_id,
                        depth + 1,
                        max_depth,
                        max_comments,
                    )

    async def get_top_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get current top stories."""
        return await self._get_story_list("topstories", limit)

    async def get_new_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get newest stories."""
        return await self._get_story_list("newstories", limit)

    async def get_best_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get best stories."""
        return await self._get_story_list("beststories", limit)

    async def get_ask_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get Ask HN stories."""
        return await self._get_story_list("askstories", limit)

    async def get_show_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get Show HN stories."""
        return await self._get_story_list("showstories", limit)

    async def get_job_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get job postings."""
        return await self._get_story_list("jobstories", limit)

    async def _get_story_list(
        self,
        list_name: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Get stories from a Firebase list."""
        client = await self._get_client()
        await self._rate_limit()

        url = f"{self.FIREBASE_BASE}/{list_name}.json"

        try:
            response = await client.get(url)
            response.raise_for_status()
            item_ids = response.json()

            if item_ids:
                return await self.get_items(item_ids[:limit])

        except Exception as e:
            logger.error(f"HackerNews: Failed to get {list_name}: {e}")

        return []

    async def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user profile."""
        client = await self._get_client()
        await self._rate_limit()

        url = f"{self.FIREBASE_BASE}/user/{username}.json"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if data:
                return {
                    "id": data.get("id"),
                    "username": data.get("id"),
                    "created_at": data.get("created"),
                    "karma": data.get("karma", 0),
                    "about": data.get("about", ""),
                    "submitted": data.get("submitted", []),
                }

        except Exception as e:
            logger.error(f"HackerNews: Failed to get user {username}: {e}")

        return None

    def _parse_algolia_hit(self, hit: Dict) -> Optional[Dict[str, Any]]:
        """Parse Algolia search result."""
        try:
            return {
                "id": int(hit.get("objectID")),
                "item_id": int(hit.get("objectID")),
                "platform": "hackernews",
                "type": hit.get("type", "story") if not hit.get("story_id") else "comment",
                "item_type": hit.get("type", "story") if not hit.get("story_id") else "comment",
                "author": hit.get("author", ""),
                "by": hit.get("author", ""),
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "text": hit.get("story_text") or hit.get("comment_text", ""),
                "content": hit.get("story_text") or hit.get("comment_text", ""),
                "created_at": hit.get("created_at_i"),
                "time": hit.get("created_at_i"),
                "points": hit.get("points", 0),
                "score": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "descendants": hit.get("num_comments", 0),
                "story_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "collected_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"HackerNews: Failed to parse hit: {e}")
            return None

    def _parse_firebase_item(self, item: Dict) -> Optional[Dict[str, Any]]:
        """Parse Firebase item."""
        try:
            item_type = item.get("type", "story")
            return {
                "id": item.get("id"),
                "item_id": item.get("id"),
                "platform": "hackernews",
                "type": item_type,
                "item_type": item_type,
                "author": item.get("by", ""),
                "by": item.get("by", ""),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "text": item.get("text", ""),
                "content": item.get("text", ""),
                "created_at": item.get("time"),
                "time": item.get("time"),
                "points": item.get("score", 0),
                "score": item.get("score", 0),
                "num_comments": item.get("descendants", 0),
                "descendants": item.get("descendants", 0),
                "kids": item.get("kids", []),
                "parent": item.get("parent"),
                "story_url": f"https://news.ycombinator.com/item?id={item.get('id')}",
                "collected_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"HackerNews: Failed to parse item: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
