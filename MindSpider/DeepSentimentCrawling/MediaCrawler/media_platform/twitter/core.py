"""
Twitter/X crawler using twikit library.

Features:
- Cookie-based authentication (no API keys needed)
- Search tweets by keyword
- Anti-bot protection via rate limiting and user agent rotation
- Cloudflare bypass via twikit's built-in mechanisms
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from twikit import Client
    from twikit.errors import TooManyRequests, Unauthorized
    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False
    Client = None
    TooManyRequests = Exception
    Unauthorized = Exception

from playwright.async_api import BrowserContext, BrowserType

# Import base classes
from ...base.base_crawler import AbstractCrawler

# Import config
try:
    from config import settings
except ImportError:
    settings = None


class TwitterCrawler(AbstractCrawler):
    """
    Twitter/X crawler using twikit library.

    Twikit uses cookie-based authentication which bypasses most anti-bot
    protections including Cloudflare. Rate limiting is handled internally.
    """

    platform = "twitter"

    def __init__(self):
        if not TWIKIT_AVAILABLE:
            raise ImportError(
                "twikit not installed. Install with: pip install twikit>=2.0.0"
            )

        self.client = Client('en-US')
        self.is_logged_in = False
        self.keyword = ""
        self.max_results = 50
        self.cookies_path = None

        # Rate limiting settings
        self.rate_limit_delay = 2.0
        self.max_requests_per_hour = 100
        self._request_count = 0
        self._hour_start = datetime.now()

        # Load config if available
        if settings:
            self.rate_limit_delay = settings.WESTERN_CRAWLER_RATE_LIMIT_DELAY
            self.max_requests_per_hour = settings.WESTERN_CRAWLER_MAX_REQUESTS_PER_HOUR
            self.cookies_path = settings.TWITTER_COOKIES_PATH

    async def start(self):
        """
        Initialize crawler and authenticate.

        Tries authentication in order:
        1. Load cookies from file (if path configured)
        2. Login with username/email/password
        """
        logger.info("Starting Twitter crawler...")

        # Try loading cookies first
        if self.cookies_path and Path(self.cookies_path).exists():
            try:
                self.client.load_cookies(self.cookies_path)
                self.is_logged_in = True
                logger.info("Twitter: Loaded cookies from file")
                return
            except Exception as e:
                logger.warning(f"Twitter: Failed to load cookies: {e}")

        # Try login with credentials
        if settings and all([
            settings.TWITTER_USERNAME,
            settings.TWITTER_EMAIL,
            settings.TWITTER_PASSWORD
        ]):
            try:
                await self.client.login(
                    auth_info_1=settings.TWITTER_USERNAME,
                    auth_info_2=settings.TWITTER_EMAIL,
                    password=settings.TWITTER_PASSWORD
                )
                self.is_logged_in = True
                logger.info("Twitter: Login successful")

                # Save cookies for future use
                if self.cookies_path:
                    self.client.save_cookies(self.cookies_path)
                    logger.info(f"Twitter: Saved cookies to {self.cookies_path}")
            except Unauthorized as e:
                logger.error(f"Twitter: Authentication failed: {e}")
                raise
            except Exception as e:
                logger.error(f"Twitter: Login error: {e}")
                raise
        else:
            logger.warning(
                "Twitter: No credentials configured. "
                "Set TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD in .env"
            )

    async def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        # Reset counter if hour has passed
        now = datetime.now()
        if (now - self._hour_start).seconds >= 3600:
            self._request_count = 0
            self._hour_start = now

        # Check if we've hit the limit
        if self._request_count >= self.max_requests_per_hour:
            wait_time = 3600 - (now - self._hour_start).seconds
            logger.warning(f"Twitter: Rate limit reached, waiting {wait_time}s")
            await asyncio.sleep(wait_time)
            self._request_count = 0
            self._hour_start = datetime.now()

        # Add delay between requests
        await asyncio.sleep(self.rate_limit_delay)
        self._request_count += 1

    async def search(self) -> List[Dict[str, Any]]:
        """
        Search tweets by keyword.

        Returns:
            List of tweet dictionaries with standardized fields
        """
        if not self.is_logged_in:
            logger.warning("Twitter: Not logged in, attempting login...")
            await self.start()

        if not self.keyword:
            logger.error("Twitter: No keyword set for search")
            return []

        results = []
        logger.info(f"Twitter: Searching for '{self.keyword}'...")

        try:
            await self._check_rate_limit()

            # Search tweets using twikit
            tweets = await self.client.search_tweet(
                self.keyword,
                product='Latest'  # 'Top' or 'Latest'
            )

            count = 0
            for tweet in tweets:
                if count >= self.max_results:
                    break

                result = self._parse_tweet(tweet)
                if result:
                    results.append(result)
                    count += 1

            logger.info(f"Twitter: Found {len(results)} tweets")

        except TooManyRequests as e:
            logger.warning(f"Twitter: Rate limited, waiting...")
            await asyncio.sleep(60)  # Wait 1 minute
            return await self.search()  # Retry
        except Exception as e:
            logger.error(f"Twitter: Search error: {e}")

        return results

    def _parse_tweet(self, tweet) -> Optional[Dict[str, Any]]:
        """Parse twikit tweet object into standardized dictionary."""
        try:
            return {
                "id": tweet.id,
                "platform": self.platform,
                "content": tweet.text,
                "author": tweet.user.screen_name if tweet.user else "unknown",
                "author_id": tweet.user.id if tweet.user else None,
                "author_name": tweet.user.name if tweet.user else None,
                "created_at": tweet.created_at,
                "retweet_count": tweet.retweet_count or 0,
                "like_count": tweet.favorite_count or 0,
                "reply_count": tweet.reply_count or 0,
                "quote_count": tweet.quote_count or 0,
                "view_count": getattr(tweet, 'view_count', 0) or 0,
                "language": getattr(tweet, 'lang', None),
                "url": f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}" if tweet.user else None,
                "collected_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Twitter: Failed to parse tweet: {e}")
            return None

    async def get_tweet_replies(self, tweet_id: str) -> List[Dict[str, Any]]:
        """
        Get replies to a specific tweet.

        Args:
            tweet_id: ID of the tweet to get replies for

        Returns:
            List of reply dictionaries
        """
        replies = []

        try:
            await self._check_rate_limit()
            tweet = await self.client.get_tweet_by_id(tweet_id)

            if tweet and hasattr(tweet, 'replies'):
                for reply in tweet.replies:
                    parsed = self._parse_tweet(reply)
                    if parsed:
                        parsed["parent_id"] = tweet_id
                        replies.append(parsed)
        except Exception as e:
            logger.error(f"Twitter: Failed to get replies for {tweet_id}: {e}")

        return replies

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True
    ) -> BrowserContext:
        """
        Launch browser for CDP mode (optional, twikit handles most cases).

        This is provided for compatibility with the AbstractCrawler interface
        but twikit's cookie-based auth typically doesn't require browser automation.
        """
        browser = await chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
        )

        context_kwargs = {}
        if user_agent:
            context_kwargs["user_agent"] = user_agent
        if playwright_proxy:
            context_kwargs["proxy"] = playwright_proxy

        context = await browser.new_context(**context_kwargs)

        # Inject stealth script if available
        stealth_path = Path(current_dir).parent.parent.parent / "libs" / "stealth.min.js"
        if stealth_path.exists():
            await context.add_init_script(path=str(stealth_path))

        return context

    async def close(self):
        """Clean up resources."""
        # twikit client doesn't require explicit cleanup
        logger.info("Twitter crawler closed")
