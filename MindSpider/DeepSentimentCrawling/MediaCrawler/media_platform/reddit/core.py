"""
Reddit crawler using PRAW (Python Reddit API Wrapper).

Features:
- OAuth-based authentication (official API)
- Search posts across all subreddits or specific ones
- Rate limiting handled by PRAW automatically
- No Cloudflare issues (official API)
"""

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import praw
    from praw.exceptions import RedditAPIException
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    praw = None
    RedditAPIException = Exception

from playwright.async_api import BrowserContext, BrowserType

# Import base classes
from ...base.base_crawler import AbstractCrawler

# Import config
try:
    from config import settings
except ImportError:
    settings = None


class RedditCrawler(AbstractCrawler):
    """
    Reddit crawler using PRAW library.

    PRAW handles OAuth authentication and rate limiting automatically.
    This is the recommended way to access Reddit data.
    """

    platform = "reddit"

    def __init__(self):
        if not PRAW_AVAILABLE:
            raise ImportError(
                "praw not installed. Install with: pip install praw>=7.7.0"
            )

        self.reddit = None
        self.is_initialized = False
        self.keyword = ""
        self.max_results = 50
        self.subreddit = "all"  # Search all subreddits by default
        self.time_filter = "week"  # hour, day, week, month, year, all
        self.sort = "relevance"  # relevance, hot, top, new, comments

        # Thread pool for running sync PRAW in async context
        self._executor = ThreadPoolExecutor(max_workers=3)

    async def start(self):
        """
        Initialize Reddit API client with OAuth credentials.
        """
        logger.info("Starting Reddit crawler...")

        if not settings or not all([
            settings.REDDIT_CLIENT_ID,
            settings.REDDIT_CLIENT_SECRET
        ]):
            logger.error(
                "Reddit: Missing credentials. "
                "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env"
            )
            raise ValueError("Reddit credentials not configured")

        try:
            self.reddit = praw.Reddit(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_CLIENT_SECRET,
                user_agent=settings.REDDIT_USER_AGENT
            )
            self.is_initialized = True
            logger.info("Reddit: API client initialized successfully")
        except Exception as e:
            logger.error(f"Reddit: Failed to initialize: {e}")
            raise

    def _search_sync(self) -> List[Dict[str, Any]]:
        """
        Synchronous search implementation (PRAW is not async-native).
        """
        results = []

        if not self.reddit or not self.keyword:
            return results

        try:
            subreddit = self.reddit.subreddit(self.subreddit)

            for submission in subreddit.search(
                self.keyword,
                limit=self.max_results,
                sort=self.sort,
                time_filter=self.time_filter
            ):
                result = self._parse_submission(submission)
                if result:
                    results.append(result)

        except RedditAPIException as e:
            logger.error(f"Reddit API error: {e}")
        except Exception as e:
            logger.error(f"Reddit search error: {e}")

        return results

    async def search(self) -> List[Dict[str, Any]]:
        """
        Search Reddit posts by keyword.

        Returns:
            List of post dictionaries with standardized fields
        """
        if not self.is_initialized:
            await self.start()

        if not self.keyword:
            logger.error("Reddit: No keyword set for search")
            return []

        logger.info(f"Reddit: Searching for '{self.keyword}' in r/{self.subreddit}...")

        # Run sync PRAW in thread pool
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(self._executor, self._search_sync)

        logger.info(f"Reddit: Found {len(results)} posts")
        return results

    def _parse_submission(self, submission) -> Optional[Dict[str, Any]]:
        """Parse PRAW submission object into standardized dictionary."""
        try:
            return {
                "id": submission.id,
                "platform": self.platform,
                "title": submission.title,
                "content": submission.selftext or "",
                "author": str(submission.author) if submission.author else "[deleted]",
                "subreddit": str(submission.subreddit),
                "score": submission.score,
                "upvote_ratio": submission.upvote_ratio,
                "num_comments": submission.num_comments,
                "created_at": datetime.fromtimestamp(submission.created_utc).isoformat(),
                "url": submission.url,
                "permalink": f"https://reddit.com{submission.permalink}",
                "is_self": submission.is_self,
                "over_18": submission.over_18,
                "spoiler": submission.spoiler,
                "stickied": submission.stickied,
                "collected_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Reddit: Failed to parse submission: {e}")
            return None

    def _get_comments_sync(self, post_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get comments for a post (sync)."""
        comments = []

        try:
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)  # Don't load "more comments"

            for comment in submission.comments.list()[:limit]:
                parsed = self._parse_comment(comment, post_id)
                if parsed:
                    comments.append(parsed)
        except Exception as e:
            logger.error(f"Reddit: Failed to get comments for {post_id}: {e}")

        return comments

    async def get_comments(self, post_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get comments for a Reddit post.

        Args:
            post_id: Reddit post ID
            limit: Maximum number of comments to fetch

        Returns:
            List of comment dictionaries
        """
        if not self.is_initialized:
            await self.start()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._get_comments_sync,
            post_id,
            limit
        )

    def _parse_comment(self, comment, post_id: str) -> Optional[Dict[str, Any]]:
        """Parse PRAW comment object into standardized dictionary."""
        try:
            return {
                "id": comment.id,
                "platform": self.platform,
                "post_id": post_id,
                "content": comment.body,
                "author": str(comment.author) if comment.author else "[deleted]",
                "score": comment.score,
                "created_at": datetime.fromtimestamp(comment.created_utc).isoformat(),
                "parent_id": comment.parent_id,
                "is_submitter": comment.is_submitter,
                "collected_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Reddit: Failed to parse comment: {e}")
            return None

    async def get_subreddit_posts(
        self,
        subreddit_name: str,
        sort: str = "hot",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get posts from a specific subreddit.

        Args:
            subreddit_name: Name of subreddit (without r/)
            sort: Sort method (hot, new, top, rising)
            limit: Maximum posts to fetch

        Returns:
            List of post dictionaries
        """
        if not self.is_initialized:
            await self.start()

        def fetch():
            results = []
            subreddit = self.reddit.subreddit(subreddit_name)

            if sort == "hot":
                posts = subreddit.hot(limit=limit)
            elif sort == "new":
                posts = subreddit.new(limit=limit)
            elif sort == "top":
                posts = subreddit.top(limit=limit, time_filter="week")
            elif sort == "rising":
                posts = subreddit.rising(limit=limit)
            else:
                posts = subreddit.hot(limit=limit)

            for post in posts:
                parsed = self._parse_submission(post)
                if parsed:
                    results.append(parsed)
            return results

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, fetch)

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True
    ) -> BrowserContext:
        """
        Launch browser (not typically needed for Reddit API access).

        This is provided for compatibility with AbstractCrawler interface.
        """
        browser = await chromium.launch(headless=headless)
        context_kwargs = {}
        if user_agent:
            context_kwargs["user_agent"] = user_agent
        if playwright_proxy:
            context_kwargs["proxy"] = playwright_proxy
        return await browser.new_context(**context_kwargs)

    async def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        logger.info("Reddit crawler closed")
