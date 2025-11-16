#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter/X Crawler Module - Updated for 2025
Uses twikit (actively maintained, works with Twitter's current API)

MIGRATION NOTICE: This replaces the ntscraper implementation which is no longer functional.

Options implemented:
1. twikit - Free scraping (requires Twitter account)
2. Apify API - Paid scraping (~$0.30 per 1000 tweets)

For 100 publishers at daily updates:
- twikit: Free but requires maintenance
- Apify: ~$10-20/month, more reliable
"""

import asyncio
import os
import time
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Conditional imports
try:
    from twikit import Client as TwikitClient
    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False
    logger.warning("twikit not installed. Install with: pip install twikit")

try:
    import httpx
    APIFY_AVAILABLE = True
except ImportError:
    APIFY_AVAILABLE = False


class TwitterCrawler:
    """
    Twitter/X crawler with multiple backend options:

    1. twikit (free, requires account)
    2. Apify API (paid, ~$0.30 per 1000 tweets)

    Usage:
        # Option 1: twikit (free)
        crawler = TwitterCrawler(method='twikit')

        # Option 2: Apify (paid)
        crawler = TwitterCrawler(method='apify', apify_api_key='your_key')
    """

    def __init__(
        self,
        method: str = 'twikit',
        rate_limit_delay: float = 10.0,
        apify_api_key: Optional[str] = None,
        twitter_username: Optional[str] = None,
        twitter_email: Optional[str] = None,
        twitter_password: Optional[str] = None,
        cookies_file: str = 'twitter_cookies.json'
    ):
        """
        Initialize Twitter crawler

        Args:
            method: 'twikit' (free) or 'apify' (paid)
            rate_limit_delay: Delay between requests in seconds
            apify_api_key: Apify API key (required if method='apify')
            twitter_username: Twitter username (required if method='twikit')
            twitter_email: Twitter email (required if method='twikit')
            twitter_password: Twitter password (required if method='twikit')
            cookies_file: Path to cookies JSON file (for twikit)
        """
        self.method = method.lower()
        self.rate_limit_delay = rate_limit_delay
        self.cookies_file = cookies_file

        # Load from env if not provided
        self.apify_api_key = apify_api_key or os.getenv('APIFY_API_KEY')
        self.twitter_username = twitter_username or os.getenv('TWITTER_USERNAME')
        self.twitter_email = twitter_email or os.getenv('TWITTER_EMAIL')
        self.twitter_password = twitter_password or os.getenv('TWITTER_PASSWORD')

        self.client = None
        self._initialized = False

        # Validate method
        if self.method not in ['twikit', 'apify']:
            raise ValueError(f"Invalid method: {method}. Must be 'twikit' or 'apify'")

        # Validate credentials
        if self.method == 'twikit':
            if not TWIKIT_AVAILABLE:
                raise ImportError("twikit not installed. Run: pip install twikit")
            if not all([self.twitter_username, self.twitter_email, self.twitter_password]):
                raise ValueError(
                    "twikit method requires TWITTER_USERNAME, TWITTER_EMAIL, "
                    "and TWITTER_PASSWORD in .env or as arguments"
                )
        elif self.method == 'apify':
            if not APIFY_AVAILABLE:
                raise ImportError("httpx not installed. Run: pip install httpx")
            if not self.apify_api_key:
                raise ValueError("Apify method requires APIFY_API_KEY in .env or as argument")

        logger.info(f"Twitter crawler initialized with method: {self.method}")

    async def initialize(self):
        """Initialize the crawler (login for twikit, validate for apify)"""
        if self._initialized:
            return

        if self.method == 'twikit':
            await self._init_twikit()
        elif self.method == 'apify':
            await self._init_apify()

        self._initialized = True

    async def _init_twikit(self):
        """Initialize twikit client with login"""
        logger.info("Initializing twikit client...")

        self.client = TwikitClient('en-US')

        # Try to load cookies first (avoid re-login)
        if os.path.exists(self.cookies_file):
            try:
                self.client.load_cookies(self.cookies_file)
                logger.info("✓ Loaded cookies from file")
                self._initialized = True
                return
            except Exception as e:
                logger.warning(f"Failed to load cookies: {e}. Will login fresh.")

        # Login if no cookies or cookies failed
        try:
            logger.info("Logging in to Twitter...")
            await self.client.login(
                auth_info_1=self.twitter_username,
                auth_info_2=self.twitter_email,
                password=self.twitter_password
            )

            # Save cookies for next time
            self.client.save_cookies(self.cookies_file)
            logger.info("✓ Logged in successfully and saved cookies")

        except Exception as e:
            logger.error(f"Failed to login: {e}")
            raise

    async def _init_apify(self):
        """Initialize Apify API client"""
        logger.info("Initializing Apify client...")

        # Test API key
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"https://api.apify.com/v2/users/me",
                    headers={"Authorization": f"Bearer {self.apify_api_key}"}
                )
                response.raise_for_status()
                logger.info("✓ Apify API key validated")
            except Exception as e:
                logger.error(f"Invalid Apify API key: {e}")
                raise ValueError("Invalid APIFY_API_KEY")

    def _parse_tweet_twikit(self, tweet) -> Optional[Dict]:
        """Parse twikit tweet object to database format"""
        try:
            return {
                'tweet_id': tweet.id,
                'author_username': tweet.user.screen_name,
                'author_name': tweet.user.name,
                'content': tweet.text[:2000],
                'created_at': int(tweet.created_at_datetime.timestamp()),
                'retweet_count': tweet.retweet_count or 0,
                'like_count': tweet.favorite_count or 0,
                'reply_count': tweet.reply_count or 0,
                'quote_count': tweet.quote_count or 0,
                'impression_count': tweet.view_count or 0,
                'hashtags': json.dumps([tag for tag in tweet.hashtags] if tweet.hashtags else []),
                'urls': json.dumps([url for url in tweet.urls] if tweet.urls else []),
                'media_urls': json.dumps([media.url for media in tweet.media] if tweet.media else []),
                'language': tweet.lang or 'en',
                'is_retweet': 1 if hasattr(tweet, 'retweeted_tweet') else 0,
                'is_reply': 1 if tweet.in_reply_to_user_id else 0,
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp())
            }
        except Exception as e:
            logger.error(f"Failed to parse tweet: {e}")
            return None

    async def get_user_tweets_twikit(
        self,
        username: str,
        count: int = 20
    ) -> List[Dict]:
        """Get tweets from a user using twikit"""
        if not self._initialized:
            await self.initialize()

        logger.info(f"Fetching {count} tweets from @{username} (twikit)...")

        try:
            # Get user
            user = await self.client.get_user_by_screen_name(username)

            # Get tweets
            tweets = await user.get_tweets('Tweets', count=count)

            # Parse tweets
            parsed_tweets = []
            for tweet in tweets:
                parsed = self._parse_tweet_twikit(tweet)
                if parsed:
                    parsed_tweets.append(parsed)

            await asyncio.sleep(self.rate_limit_delay)

            logger.info(f"✓ Fetched {len(parsed_tweets)} tweets from @{username}")
            return parsed_tweets

        except Exception as e:
            logger.error(f"Failed to fetch tweets from @{username}: {e}")
            return []

    async def get_user_tweets_apify(
        self,
        username: str,
        count: int = 20
    ) -> List[Dict]:
        """Get tweets from a user using Apify API"""
        if not self._initialized:
            await self.initialize()

        logger.info(f"Fetching {count} tweets from @{username} (Apify)...")

        # Apify Actor: twitter-scraper
        actor_id = "apidojo/tweet-scraper"

        payload = {
            "searchMode": "user",
            "searchTerms": [username],
            "maxTweets": count,
            "addUserInfo": True
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Start actor run
                response = await client.post(
                    f"https://api.apify.com/v2/acts/{actor_id}/runs",
                    headers={"Authorization": f"Bearer {self.apify_api_key}"},
                    json=payload
                )
                response.raise_for_status()
                run_data = response.json()
                run_id = run_data['data']['id']

                # Wait for completion
                logger.info(f"Waiting for Apify run {run_id}...")
                await asyncio.sleep(5)  # Give it time to start

                # Get results
                response = await client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items",
                    headers={"Authorization": f"Bearer {self.apify_api_key}"}
                )
                response.raise_for_status()
                tweets_data = response.json()

                # Parse results
                parsed_tweets = []
                for tweet in tweets_data:
                    parsed = {
                        'tweet_id': tweet.get('id', ''),
                        'author_username': tweet.get('author', {}).get('userName', ''),
                        'author_name': tweet.get('author', {}).get('name', ''),
                        'content': tweet.get('text', '')[:2000],
                        'created_at': int(datetime.fromisoformat(
                            tweet.get('createdAt', '').replace('Z', '+00:00')
                        ).timestamp()) if tweet.get('createdAt') else 0,
                        'retweet_count': tweet.get('retweetCount', 0),
                        'like_count': tweet.get('likeCount', 0),
                        'reply_count': tweet.get('replyCount', 0),
                        'quote_count': tweet.get('quoteCount', 0),
                        'impression_count': tweet.get('viewCount', 0),
                        'hashtags': json.dumps(tweet.get('hashtags', [])),
                        'urls': json.dumps(tweet.get('urls', [])),
                        'media_urls': json.dumps([m.get('url') for m in tweet.get('media', [])]),
                        'language': tweet.get('lang', 'en'),
                        'is_retweet': 1 if tweet.get('isRetweet') else 0,
                        'is_reply': 1 if tweet.get('isReply') else 0,
                        'add_ts': int(datetime.now().timestamp()),
                        'last_modify_ts': int(datetime.now().timestamp())
                    }
                    parsed_tweets.append(parsed)

                await asyncio.sleep(self.rate_limit_delay)

                logger.info(f"✓ Fetched {len(parsed_tweets)} tweets from @{username}")
                return parsed_tweets

        except Exception as e:
            logger.error(f"Apify API error for @{username}: {e}")
            return []

    async def get_user_tweets(self, username: str, count: int = 20) -> List[Dict]:
        """
        Get tweets from a user (uses configured method)

        Args:
            username: Twitter username (without @)
            count: Number of tweets to fetch

        Returns:
            List of parsed tweets
        """
        if self.method == 'twikit':
            return await self.get_user_tweets_twikit(username, count)
        elif self.method == 'apify':
            return await self.get_user_tweets_apify(username, count)

    async def monitor_publishers(
        self,
        publishers: List[str],
        tweets_per_publisher: int = 10
    ) -> Dict:
        """
        Monitor tweets from multiple publishers

        Args:
            publishers: List of Twitter usernames
            tweets_per_publisher: Number of tweets per publisher

        Returns:
            Dictionary with all tweets
        """
        logger.info(f"Monitoring {len(publishers)} publishers...")

        all_tweets = []

        for username in publishers:
            try:
                tweets = await self.get_user_tweets(username, count=tweets_per_publisher)
                all_tweets.extend(tweets)
            except Exception as e:
                logger.error(f"Failed to fetch from @{username}: {e}")
                continue

        logger.info(f"✓ Monitoring complete: {len(all_tweets)} total tweets")

        return {
            'tweets': all_tweets,
            'total_tweets': len(all_tweets),
            'publishers_monitored': len(publishers)
        }

    async def close(self):
        """Clean up resources"""
        if self.method == 'twikit' and self.client:
            # Save cookies before closing
            try:
                self.client.save_cookies(self.cookies_file)
            except:
                pass


async def main():
    """Test Twitter crawler"""
    logger.info("Testing Twitter Crawler (2025 version)...")

    # Determine which method to test
    if os.getenv('APIFY_API_KEY'):
        logger.info("Testing with Apify API (paid)...")
        crawler = TwitterCrawler(method='apify')
    elif all([os.getenv('TWITTER_USERNAME'), os.getenv('TWITTER_EMAIL'),
              os.getenv('TWITTER_PASSWORD')]):
        logger.info("Testing with twikit (free)...")
        crawler = TwitterCrawler(method='twikit')
    else:
        logger.error(
            "No credentials found!\n"
            "For twikit: Set TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD\n"
            "For Apify: Set APIFY_API_KEY"
        )
        return

    try:
        # Test with a few publishers
        test_publishers = ['CNN', 'BBCNews', 'Reuters']

        result = await crawler.monitor_publishers(
            publishers=test_publishers,
            tweets_per_publisher=5
        )

        logger.info(f"\n✓ Test complete!")
        logger.info(f"  Publishers: {result['publishers_monitored']}")
        logger.info(f"  Total tweets: {result['total_tweets']}")

        # Show sample
        if result['tweets']:
            logger.info("\nSample tweets:")
            for tweet in result['tweets'][:3]:
                logger.info(f"  @{tweet['author_username']}: {tweet['content'][:100]}...")

    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
