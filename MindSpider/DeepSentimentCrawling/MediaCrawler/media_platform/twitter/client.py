# -*- coding: utf-8 -*-
"""
Twitter/X API client wrapper using twikit.

Provides a unified interface for Twitter operations with rate limiting
and cookie-based authentication.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# Add project root to path
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

try:
    from config import settings
except ImportError:
    settings = None


class TwitterClient:
    """
    Twitter API client wrapper with rate limiting and auth management.

    Uses twikit's cookie-based authentication for anti-bot bypass.
    """

    def __init__(
        self,
        cookies_path: Optional[str] = None,
        rate_limit_delay: float = 2.0,
        max_requests_per_hour: int = 100,
    ):
        if not TWIKIT_AVAILABLE:
            raise ImportError(
                "twikit not installed. Install with: pip install twikit>=2.0.0"
            )

        self.client = Client('en-US')
        self.is_authenticated = False
        self.cookies_path = cookies_path

        # Rate limiting
        self.rate_limit_delay = rate_limit_delay
        self.max_requests_per_hour = max_requests_per_hour
        self._request_count = 0
        self._hour_start = datetime.now()

        # Load config defaults
        if settings:
            if not cookies_path:
                self.cookies_path = settings.TWITTER_COOKIES_PATH
            self.rate_limit_delay = settings.WESTERN_CRAWLER_RATE_LIMIT_DELAY
            self.max_requests_per_hour = settings.WESTERN_CRAWLER_MAX_REQUESTS_PER_HOUR

    async def _check_rate_limit(self):
        """Enforce rate limiting between requests."""
        now = datetime.now()
        if (now - self._hour_start).seconds >= 3600:
            self._request_count = 0
            self._hour_start = now

        if self._request_count >= self.max_requests_per_hour:
            wait_time = 3600 - (now - self._hour_start).seconds
            logger.warning(f"Twitter rate limit reached, waiting {wait_time}s")
            await asyncio.sleep(wait_time)
            self._request_count = 0
            self._hour_start = datetime.now()

        await asyncio.sleep(self.rate_limit_delay)
        self._request_count += 1

    async def authenticate(
        self,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """
        Authenticate with Twitter.

        Tries in order:
        1. Load existing cookies from file
        2. Login with provided credentials
        3. Login with config credentials

        Returns:
            True if authentication successful
        """
        # Try loading cookies first
        if self.cookies_path and Path(self.cookies_path).exists():
            try:
                self.client.load_cookies(self.cookies_path)
                self.is_authenticated = True
                logger.info("Twitter: Loaded cookies from file")
                return True
            except Exception as e:
                logger.warning(f"Twitter: Failed to load cookies: {e}")

        # Get credentials
        auth_username = username
        auth_email = email
        auth_password = password

        if not all([auth_username, auth_email, auth_password]) and settings:
            auth_username = auth_username or settings.TWITTER_USERNAME
            auth_email = auth_email or settings.TWITTER_EMAIL
            auth_password = auth_password or settings.TWITTER_PASSWORD

        if not all([auth_username, auth_email, auth_password]):
            logger.error(
                "Twitter: No credentials available. "
                "Set TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD"
            )
            return False

        # Login
        try:
            await self.client.login(
                auth_info_1=auth_username,
                auth_info_2=auth_email,
                password=auth_password
            )
            self.is_authenticated = True
            logger.info("Twitter: Login successful")

            # Save cookies
            if self.cookies_path:
                self.client.save_cookies(self.cookies_path)
                logger.info(f"Twitter: Saved cookies to {self.cookies_path}")

            return True
        except Unauthorized as e:
            logger.error(f"Twitter: Authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Twitter: Login error: {e}")
            return False

    async def search_tweets(
        self,
        query: str,
        max_results: int = 50,
        product: str = 'Latest',
    ) -> List[Dict[str, Any]]:
        """
        Search for tweets matching query.

        Args:
            query: Search query string
            max_results: Maximum tweets to return
            product: 'Latest' or 'Top'

        Returns:
            List of tweet dictionaries
        """
        if not self.is_authenticated:
            logger.warning("Twitter: Not authenticated, attempting login...")
            if not await self.authenticate():
                return []

        results = []
        try:
            await self._check_rate_limit()
            tweets = await self.client.search_tweet(query, product=product)

            count = 0
            for tweet in tweets:
                if count >= max_results:
                    break
                parsed = self._parse_tweet(tweet)
                if parsed:
                    results.append(parsed)
                    count += 1

            logger.info(f"Twitter: Found {len(results)} tweets for '{query}'")

        except TooManyRequests:
            logger.warning("Twitter: Rate limited, waiting 60s...")
            await asyncio.sleep(60)
            return await self.search_tweets(query, max_results, product)
        except Exception as e:
            logger.error(f"Twitter: Search error: {e}")

        return results

    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get a single tweet by ID."""
        if not self.is_authenticated:
            if not await self.authenticate():
                return None

        try:
            await self._check_rate_limit()
            tweet = await self.client.get_tweet_by_id(tweet_id)
            return self._parse_tweet(tweet) if tweet else None
        except Exception as e:
            logger.error(f"Twitter: Failed to get tweet {tweet_id}: {e}")
            return None

    async def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user profile by username."""
        if not self.is_authenticated:
            if not await self.authenticate():
                return None

        try:
            await self._check_rate_limit()
            user = await self.client.get_user_by_screen_name(username)
            return self._parse_user(user) if user else None
        except Exception as e:
            logger.error(f"Twitter: Failed to get user {username}: {e}")
            return None

    async def get_user_tweets(
        self,
        user_id: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get tweets from a specific user."""
        if not self.is_authenticated:
            if not await self.authenticate():
                return []

        results = []
        try:
            await self._check_rate_limit()
            tweets = await self.client.get_user_tweets(user_id, 'Tweets')

            count = 0
            for tweet in tweets:
                if count >= max_results:
                    break
                parsed = self._parse_tweet(tweet)
                if parsed:
                    results.append(parsed)
                    count += 1

        except Exception as e:
            logger.error(f"Twitter: Failed to get tweets for user {user_id}: {e}")

        return results

    def _parse_tweet(self, tweet) -> Optional[Dict[str, Any]]:
        """Parse twikit tweet object to dictionary."""
        try:
            user = tweet.user
            return {
                "id": tweet.id,
                "tweet_id": tweet.id,
                "platform": "twitter",
                "content": tweet.text,
                "author": user.screen_name if user else "unknown",
                "author_id": user.id if user else None,
                "author_name": user.name if user else None,
                "user_id": user.id if user else None,
                "username": user.screen_name if user else "unknown",
                "display_name": user.name if user else None,
                "avatar": user.profile_image_url if user else None,
                "created_at": tweet.created_at,
                "retweet_count": tweet.retweet_count or 0,
                "like_count": tweet.favorite_count or 0,
                "reply_count": tweet.reply_count or 0,
                "quote_count": tweet.quote_count or 0,
                "view_count": getattr(tweet, 'view_count', 0) or 0,
                "language": getattr(tweet, 'lang', None),
                "url": f"https://twitter.com/{user.screen_name}/status/{tweet.id}" if user else None,
                "tweet_url": f"https://twitter.com/{user.screen_name}/status/{tweet.id}" if user else None,
                "collected_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Twitter: Failed to parse tweet: {e}")
            return None

    def _parse_user(self, user) -> Optional[Dict[str, Any]]:
        """Parse twikit user object to dictionary."""
        try:
            return {
                "id": user.id,
                "user_id": user.id,
                "username": user.screen_name,
                "display_name": user.name,
                "avatar": user.profile_image_url,
                "bio": user.description,
                "location": user.location,
                "website": user.url,
                "created_at": user.created_at,
                "followers_count": user.followers_count or 0,
                "following_count": user.friends_count or 0,
                "tweet_count": user.statuses_count or 0,
                "verified": user.verified,
            }
        except Exception as e:
            logger.warning(f"Twitter: Failed to parse user: {e}")
            return None

    def save_cookies(self, path: Optional[str] = None):
        """Save authentication cookies to file."""
        save_path = path or self.cookies_path
        if save_path:
            self.client.save_cookies(save_path)
            logger.info(f"Twitter: Saved cookies to {save_path}")

    def load_cookies(self, path: Optional[str] = None) -> bool:
        """Load authentication cookies from file."""
        load_path = path or self.cookies_path
        if load_path and Path(load_path).exists():
            try:
                self.client.load_cookies(load_path)
                self.is_authenticated = True
                return True
            except Exception as e:
                logger.warning(f"Twitter: Failed to load cookies: {e}")
        return False
