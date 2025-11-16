#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter/X Crawler Module
Fetches tweets using ntscraper (no API key required)
Includes heavy rate limiting to avoid IP bans

IMPORTANT: This uses web scraping, so be very careful with rate limiting!
Recommended: Use proxy rotation if scraping frequently
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
from ntscraper import Nitter
import json


class TwitterCrawler:
    """
    Twitter/X crawler using ntscraper (Nitter instances)
    No API key required, but subject to rate limits

    CAUTION: Twitter/X aggressively blocks scrapers.
    Use conservative rate limits and consider proxy rotation!
    """

    def __init__(self, rate_limit_delay: float = 5.0):
        """
        Initialize Twitter crawler

        Args:
            rate_limit_delay: Delay between requests (MINIMUM 5 seconds recommended)
        """
        if rate_limit_delay < 3.0:
            logger.warning(
                "Rate limit delay < 3 seconds is risky for Twitter scraping! "
                "Recommend at least 5 seconds to avoid IP bans."
            )

        self.rate_limit_delay = rate_limit_delay
        self.scraper = Nitter(log_level=1)  # 1 = only errors
        logger.info(f"Twitter crawler initialized (rate limit: {rate_limit_delay}s)")

    def _parse_tweet(self, tweet_data: Dict) -> Optional[Dict]:
        """
        Parse tweet data to database format

        Args:
            tweet_data: Raw tweet data from ntscraper

        Returns:
            Formatted tweet dictionary
        """
        try:
            # Extract tweet text
            text = tweet_data.get('text', '')

            # Extract hashtags
            hashtags = []
            if 'hashtags' in tweet_data:
                hashtags = tweet_data['hashtags']

            # Extract URLs
            urls = []
            if 'entries' in tweet_data and 'urls' in tweet_data['entries']:
                urls = tweet_data['entries']['urls']

            # Extract media
            media_urls = []
            if 'entries' in tweet_data and 'photos' in tweet_data['entries']:
                media_urls = tweet_data['entries']['photos']

            return {
                'tweet_id': tweet_data.get('tweet-id', ''),
                'author_username': tweet_data.get('user', {}).get('username', ''),
                'author_name': tweet_data.get('user', {}).get('name', ''),
                'content': text[:2000],  # Limit length
                'created_at': self._parse_twitter_date(tweet_data.get('date', '')),
                'retweet_count': self._parse_stat(tweet_data.get('stats', {}).get('retweets', 0)),
                'like_count': self._parse_stat(tweet_data.get('stats', {}).get('likes', 0)),
                'reply_count': self._parse_stat(tweet_data.get('stats', {}).get('comments', 0)),
                'quote_count': self._parse_stat(tweet_data.get('stats', {}).get('quotes', 0)),
                'hashtags': json.dumps(hashtags),
                'urls': json.dumps(urls),
                'media_urls': json.dumps(media_urls),
                'language': 'en',  # Assume English, could be detected
                'is_retweet': 1 if tweet_data.get('is-retweet', False) else 0,
                'is_reply': 1 if tweet_data.get('is-reply', False) else 0,
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp())
            }
        except Exception as e:
            logger.error(f"Failed to parse tweet: {e}")
            return None

    def _parse_twitter_date(self, date_str: str) -> int:
        """Parse Twitter date string to Unix timestamp"""
        try:
            # Twitter date format: "Dec 28, 2023 · 3:45 PM UTC"
            # This is a simplified parser
            if date_str:
                # For now, just use current time
                # TODO: Implement proper date parsing
                return int(datetime.now().timestamp())
            return int(datetime.now().timestamp())
        except:
            return int(datetime.now().timestamp())

    def _parse_stat(self, stat_value) -> int:
        """Parse Twitter stat (handles 'K', 'M' suffixes)"""
        try:
            if isinstance(stat_value, int):
                return stat_value
            if isinstance(stat_value, str):
                stat_value = stat_value.replace(',', '')
                if 'K' in stat_value:
                    return int(float(stat_value.replace('K', '')) * 1000)
                elif 'M' in stat_value:
                    return int(float(stat_value.replace('M', '')) * 1000000)
                else:
                    return int(stat_value)
            return 0
        except:
            return 0

    def search_tweets(
        self,
        query: str,
        mode: str = 'term',
        limit: int = 20
    ) -> Dict:
        """
        Search for tweets by keyword

        Args:
            query: Search query (keyword, hashtag, or @username)
            mode: Search mode ('term' for keyword, 'hashtag', 'user')
            limit: Maximum number of tweets to retrieve

        Returns:
            Dictionary with tweets
        """
        logger.info(f"Searching Twitter for '{query}' (mode={mode}, limit={limit})...")
        logger.warning(
            "⚠️  Twitter scraping is high-risk for IP bans. "
            "Ensure you have proper rate limiting and consider using proxies!"
        )

        try:
            # Add delay before request
            time.sleep(self.rate_limit_delay)

            # Fetch tweets based on mode
            if mode == 'term':
                tweets = self.scraper.get_tweets(query, mode='term', number=limit)
            elif mode == 'hashtag':
                tweets = self.scraper.get_tweets(query, mode='hashtag', number=limit)
            elif mode == 'user':
                tweets = self.scraper.get_tweets(query, mode='user', number=limit)
            else:
                logger.error(f"Invalid mode: {mode}")
                return {'tweets': [], 'total_tweets': 0, 'error': 'Invalid mode'}

            # Parse tweets
            parsed_tweets = []
            if tweets and 'tweets' in tweets:
                for tweet_data in tweets['tweets']:
                    parsed = self._parse_tweet(tweet_data)
                    if parsed:
                        parsed_tweets.append(parsed)

            logger.info(f"✓ Found {len(parsed_tweets)} tweets for '{query}'")

            return {
                'tweets': parsed_tweets,
                'total_tweets': len(parsed_tweets),
                'query': query
            }

        except Exception as e:
            logger.error(f"Twitter search failed: {e}")
            return {
                'tweets': [],
                'total_tweets': 0,
                'error': str(e)
            }

    def get_user_tweets(
        self,
        username: str,
        limit: int = 20
    ) -> Dict:
        """
        Get tweets from a specific user

        Args:
            username: Twitter username (without @)
            limit: Maximum number of tweets

        Returns:
            Dictionary with tweets
        """
        logger.info(f"Fetching tweets from @{username}...")

        return self.search_tweets(query=username, mode='user', limit=limit)

    def search_hashtag(
        self,
        hashtag: str,
        limit: int = 20
    ) -> Dict:
        """
        Search tweets by hashtag

        Args:
            hashtag: Hashtag to search (with or without #)
            limit: Maximum number of tweets

        Returns:
            Dictionary with tweets
        """
        # Remove # if present
        hashtag = hashtag.lstrip('#')
        logger.info(f"Searching hashtag #{hashtag}...")

        return self.search_tweets(query=hashtag, mode='hashtag', limit=limit)

    def monitor_political_accounts(
        self,
        tweets_per_account: int = 10
    ) -> Dict:
        """
        Monitor tweets from major political figures and news accounts

        Args:
            tweets_per_account: Number of tweets to fetch per account

        Returns:
            Combined tweets from all accounts
        """
        logger.info("Monitoring political Twitter accounts...")

        # Major political and news accounts
        accounts = {
            'news': ['CNN', 'FoxNews', 'nytimes', 'washingtonpost', 'Reuters', 'AP'],
            'left': ['AOC', 'SenWarren', 'BernieSanders'],
            'right': ['RonDeSantisFL', 'tedcruz', 'mtgreenee']
        }

        all_tweets = []

        for category, usernames in accounts.items():
            logger.info(f"Fetching {category} accounts...")

            for username in usernames:
                try:
                    result = self.get_user_tweets(username, limit=tweets_per_account)
                    all_tweets.extend(result['tweets'])

                    # IMPORTANT: Heavy rate limiting between accounts
                    time.sleep(self.rate_limit_delay * 2)

                except Exception as e:
                    logger.error(f"Failed to fetch @{username}: {e}")
                    continue

        logger.info(f"Political monitoring complete: {len(all_tweets)} tweets")

        return {
            'tweets': all_tweets,
            'total_tweets': len(all_tweets)
        }


def main():
    """Test Twitter crawler"""
    logger.info("Testing Twitter/X Crawler...")
    logger.warning(
        "\n⚠️  WARNING ⚠️\n"
        "Twitter/X aggressively blocks scrapers!\n"
        "This test uses conservative rate limits to reduce ban risk.\n"
        "For production use, consider:\n"
        "  1. Using proxy rotation\n"
        "  2. Increasing delays between requests\n"
        "  3. Limiting total requests per day\n"
    )

    try:
        # Use very conservative rate limiting for testing
        crawler = TwitterCrawler(rate_limit_delay=10.0)

        # Test 1: Search for a term
        logger.info("\nTest 1: Searching for keyword...")
        result = crawler.search_tweets(
            query='artificial intelligence',
            mode='term',
            limit=5
        )

        logger.info(f"Search results: {result['total_tweets']} tweets")

        # Show sample tweets
        if result['tweets']:
            logger.info("\nSample tweets:")
            for tweet in result['tweets'][:2]:
                logger.info(f"  @{tweet['author_username']}: {tweet['content'][:100]}...")

        logger.info("\n✓ Test complete!")
        logger.info(
            "If you see tweets above, the crawler is working. "
            "Remember to use careful rate limiting in production!"
        )

    except Exception as e:
        logger.error(f"Test failed: {e}")
        logger.info(
            "\nNote: Twitter scraping may fail due to:\n"
            "  - IP rate limiting\n"
            "  - Nitter instance unavailability\n"
            "  - Network issues\n"
            "Consider using Twitter API if available."
        )


if __name__ == "__main__":
    main()
