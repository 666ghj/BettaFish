#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HackerNews Crawler Module
Fetches posts and comments from HackerNews using Firebase API
API Docs: https://github.com/HackerNews/API
"""

import asyncio
import httpx
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
import time


class HackerNewsCrawler:
    """
    HackerNews crawler using official Firebase API
    No authentication required, rate limits are generous
    """

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize HackerNews crawler

        Args:
            rate_limit_delay: Delay between API requests in seconds
        """
        self.rate_limit_delay = rate_limit_delay
        self.client = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def _get_json(self, endpoint: str) -> Optional[Dict]:
        """
        Make GET request to HackerNews API

        Args:
            endpoint: API endpoint (e.g., '/topstories.json')

        Returns:
            JSON response or None if error
        """
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            await asyncio.sleep(self.rate_limit_delay)  # Rate limiting
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    async def get_top_stories(self, limit: int = 30) -> List[int]:
        """
        Get top story IDs from HackerNews

        Args:
            limit: Number of stories to retrieve (max 500)

        Returns:
            List of story IDs
        """
        data = await self._get_json("/topstories.json")
        if data:
            return data[:limit]
        return []

    async def get_new_stories(self, limit: int = 30) -> List[int]:
        """Get new story IDs"""
        data = await self._get_json("/newstories.json")
        if data:
            return data[:limit]
        return []

    async def get_best_stories(self, limit: int = 30) -> List[int]:
        """Get best story IDs"""
        data = await self._get_json("/beststories.json")
        if data:
            return data[:limit]
        return []

    async def get_ask_stories(self, limit: int = 30) -> List[int]:
        """Get 'Ask HN' story IDs"""
        data = await self._get_json("/askstories.json")
        if data:
            return data[:limit]
        return []

    async def get_show_stories(self, limit: int = 30) -> List[int]:
        """Get 'Show HN' story IDs"""
        data = await self._get_json("/showstories.json")
        if data:
            return data[:limit]
        return []

    async def get_job_stories(self, limit: int = 30) -> List[int]:
        """Get job posting story IDs"""
        data = await self._get_json("/jobstories.json")
        if data:
            return data[:limit]
        return []

    async def get_item(self, item_id: int) -> Optional[Dict]:
        """
        Get a specific item (story, comment, etc.) by ID

        Args:
            item_id: HackerNews item ID

        Returns:
            Item data dictionary or None
        """
        return await self._get_json(f"/item/{item_id}.json")

    async def get_items_batch(self, item_ids: List[int]) -> List[Dict]:
        """
        Get multiple items in batch

        Args:
            item_ids: List of HackerNews item IDs

        Returns:
            List of item dictionaries (excluding None values)
        """
        tasks = [self.get_item(item_id) for item_id in item_ids]
        results = await asyncio.gather(*tasks)
        return [item for item in results if item is not None]

    def _parse_item_to_post(self, item: Dict) -> Optional[Dict]:
        """
        Parse HackerNews item to database post format

        Args:
            item: Raw item data from API

        Returns:
            Formatted post dictionary or None if not a story
        """
        if not item or item.get('type') not in ['story', 'job', 'poll']:
            return None

        try:
            return {
                'post_id': str(item['id']),
                'post_type': item.get('type', 'story'),
                'title': item.get('title', '')[:500],
                'author': item.get('by', 'unknown'),
                'url': item.get('url', '')[:512],
                'text': item.get('text', ''),
                'score': item.get('score', 0),
                'num_comments': len(item.get('kids', [])),
                'created_at': item.get('time', int(time.time())),
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp())
            }
        except Exception as e:
            logger.error(f"Failed to parse item {item.get('id')}: {e}")
            return None

    def _parse_item_to_comment(self, item: Dict, post_id: str) -> Optional[Dict]:
        """
        Parse HackerNews item to database comment format

        Args:
            item: Raw item data from API
            post_id: Parent post ID

        Returns:
            Formatted comment dictionary or None
        """
        if not item or item.get('type') != 'comment':
            return None

        try:
            return {
                'comment_id': str(item['id']),
                'post_id': post_id,
                'parent_id': str(item.get('parent', '')),
                'author': item.get('by', 'unknown'),
                'text': item.get('text', ''),
                'created_at': item.get('time', int(time.time())),
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp())
            }
        except Exception as e:
            logger.error(f"Failed to parse comment {item.get('id')}: {e}")
            return None

    async def crawl_stories(
        self,
        story_type: str = 'top',
        limit: int = 30,
        fetch_comments: bool = True,
        max_comments_per_story: int = 50
    ) -> Dict:
        """
        Crawl HackerNews stories with optional comments

        Args:
            story_type: Type of stories ('top', 'new', 'best', 'ask', 'show', 'job')
            limit: Number of stories to fetch
            fetch_comments: Whether to fetch comments for each story
            max_comments_per_story: Maximum comments to fetch per story

        Returns:
            Dictionary with posts and comments
        """
        logger.info(f"Crawling {limit} {story_type} stories from HackerNews...")

        # Get story IDs based on type
        story_getters = {
            'top': self.get_top_stories,
            'new': self.get_new_stories,
            'best': self.get_best_stories,
            'ask': self.get_ask_stories,
            'show': self.get_show_stories,
            'job': self.get_job_stories
        }

        getter = story_getters.get(story_type, self.get_top_stories)
        story_ids = await getter(limit)

        if not story_ids:
            logger.warning(f"No {story_type} stories found")
            return {'posts': [], 'comments': []}

        logger.info(f"Fetching {len(story_ids)} story details...")

        # Fetch story details
        stories = await self.get_items_batch(story_ids)
        posts = [self._parse_item_to_post(story) for story in stories]
        posts = [p for p in posts if p is not None]

        logger.info(f"Successfully fetched {len(posts)} stories")

        # Fetch comments if requested
        comments = []
        if fetch_comments:
            logger.info(f"Fetching comments for {len(posts)} stories...")

            for post, story in zip(posts, stories):
                if not story:
                    continue

                comment_ids = story.get('kids', [])[:max_comments_per_story]

                if comment_ids:
                    logger.info(f"Fetching {len(comment_ids)} comments for story {post['post_id']}...")
                    comment_items = await self.get_items_batch(comment_ids)

                    for item in comment_items:
                        comment = self._parse_item_to_comment(item, post['post_id'])
                        if comment:
                            comments.append(comment)

            logger.info(f"Successfully fetched {len(comments)} comments")

        return {
            'posts': posts,
            'comments': comments,
            'total_posts': len(posts),
            'total_comments': len(comments)
        }

    async def search_by_keyword(
        self,
        keyword: str,
        story_type: str = 'top',
        limit: int = 100
    ) -> Dict:
        """
        Search HackerNews stories by keyword in title

        Args:
            keyword: Keyword to search for
            story_type: Type of stories to search in
            limit: Maximum number of stories to check

        Returns:
            Dictionary with matching posts
        """
        logger.info(f"Searching for '{keyword}' in {story_type} stories...")

        # Get stories
        result = await self.crawl_stories(
            story_type=story_type,
            limit=limit,
            fetch_comments=False
        )

        # Filter by keyword
        keyword_lower = keyword.lower()
        matching_posts = [
            post for post in result['posts']
            if keyword_lower in post['title'].lower() or
            (post.get('text') and keyword_lower in post['text'].lower())
        ]

        logger.info(f"Found {len(matching_posts)} matching stories")

        return {
            'posts': matching_posts,
            'total_posts': len(matching_posts),
            'keyword': keyword
        }


async def main():
    """Test HackerNews crawler"""
    logger.info("Testing HackerNews Crawler...")

    async with HackerNewsCrawler(rate_limit_delay=0.5) as crawler:
        # Test 1: Get top stories
        result = await crawler.crawl_stories(
            story_type='top',
            limit=10,
            fetch_comments=True,
            max_comments_per_story=10
        )

        logger.info(f"\nTop Stories Results:")
        logger.info(f"  Posts: {result['total_posts']}")
        logger.info(f"  Comments: {result['total_comments']}")

        # Test 2: Search for specific keyword
        search_result = await crawler.search_by_keyword(
            keyword='AI',
            story_type='top',
            limit=50
        )

        logger.info(f"\nSearch Results for 'AI':")
        logger.info(f"  Matching posts: {search_result['total_posts']}")

        # Show sample posts
        if search_result['posts']:
            logger.info("\nSample posts:")
            for post in search_result['posts'][:3]:
                logger.info(f"  - {post['title']} (score: {post['score']})")


if __name__ == "__main__":
    asyncio.run(main())
