#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Script for Western Media Crawlers
Quick test to verify all crawlers are working correctly
"""

import asyncio
from loguru import logger
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import crawlers
try:
    from MindSpider.DeepSentimentCrawling.western_platforms import (
        HackerNewsCrawler,
        RedditCrawler,
        YouTubeCrawler,
        TwitterCrawler,
        get_rate_limiter
    )
    from MindSpider.BroadTopicExtraction.western_news_collector import WesternNewsCollector
except ImportError as e:
    logger.error(f"Failed to import crawlers: {e}")
    logger.info("Make sure you've installed all requirements: pip install -r requirements.txt")
    sys.exit(1)


async def test_hackernews():
    """Test HackerNews crawler (no API key needed)"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing HackerNews Crawler (No API key needed)")
    logger.info("=" * 60)

    try:
        async with HackerNewsCrawler(rate_limit_delay=0.5) as crawler:
            result = await crawler.crawl_stories(
                story_type='top',
                limit=5,
                fetch_comments=False
            )

            logger.info(f"✓ HackerNews: {result['total_posts']} posts fetched")
            return True
    except Exception as e:
        logger.error(f"✗ HackerNews test failed: {e}")
        return False


async def test_western_news():
    """Test Western news RSS collector"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Western News RSS Collector")
    logger.info("=" * 60)

    try:
        async with WesternNewsCollector(rate_limit_delay=1.0) as collector:
            # Test with just a few sources
            result = await collector.collect_all_western_news(
                sources=['google_news_us', 'reuters'],
                political_filter=None
            )

            logger.info(f"✓ Western News: {result['total_articles']} articles fetched")
            return True
    except Exception as e:
        logger.error(f"✗ Western News test failed: {e}")
        return False


def test_reddit():
    """Test Reddit crawler (requires API key)"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Reddit Crawler (Requires API credentials)")
    logger.info("=" * 60)

    try:
        crawler = RedditCrawler(rate_limit_delay=1.0)

        result = crawler.crawl_subreddit(
            subreddit_name='technology',
            sort='hot',
            limit=3,
            fetch_comments=False
        )

        logger.info(f"✓ Reddit: {result['total_posts']} posts fetched from r/technology")
        return True
    except ValueError as e:
        logger.warning(f"⚠ Reddit: {e}")
        logger.info("  To use Reddit: Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env")
        logger.info("  See WESTERN_MEDIA_SETUP.md for instructions")
        return False
    except Exception as e:
        logger.error(f"✗ Reddit test failed: {e}")
        return False


def test_youtube():
    """Test YouTube crawler (requires API key)"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing YouTube Crawler (Requires API key)")
    logger.info("=" * 60)

    try:
        crawler = YouTubeCrawler(rate_limit_delay=1.0)

        result = crawler.search_videos(
            query='artificial intelligence',
            max_results=3,
            order='relevance'
        )

        logger.info(f"✓ YouTube: {result['total_videos']} videos fetched")
        logger.info(f"  API quota used: {crawler.quota_used}/10000")
        return True
    except ValueError as e:
        logger.warning(f"⚠ YouTube: {e}")
        logger.info("  To use YouTube: Set YOUTUBE_API_KEY in .env")
        logger.info("  See WESTERN_MEDIA_SETUP.md for instructions")
        return False
    except Exception as e:
        logger.error(f"✗ YouTube test failed: {e}")
        return False


def test_twitter():
    """Test Twitter crawler (no API needed, but risky)"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Twitter Crawler (Scraper - High risk of IP ban!)")
    logger.info("=" * 60)

    logger.warning("⚠️  Twitter scraping is HIGH RISK for IP bans!")
    logger.warning("⚠️  This test is DISABLED by default for safety.")
    logger.warning("⚠️  Uncomment in test_western_crawlers.py to enable (not recommended)")

    # Disabled by default to protect IP
    return None

    # Uncomment below to test (NOT RECOMMENDED from home IP):
    # try:
    #     crawler = TwitterCrawler(rate_limit_delay=15.0)  # Very conservative
    #
    #     result = crawler.search_tweets(
    #         query='AI',
    #         mode='term',
    #         limit=3
    #     )
    #
    #     logger.info(f"✓ Twitter: {result['total_tweets']} tweets fetched")
    #     return True
    # except Exception as e:
    #     logger.error(f"✗ Twitter test failed: {e}")
    #     return False


async def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("Western Media Crawlers - Test Suite")
    logger.info("=" * 60)
    logger.info("This will test all Western media crawlers with minimal requests")
    logger.info("")

    results = {}

    # Tests that don't require API keys
    logger.info("Running tests for platforms without API requirements...")
    results['hackernews'] = await test_hackernews()
    results['western_news'] = await test_western_news()

    # Tests that require API keys
    logger.info("\nRunning tests for platforms with API requirements...")
    results['reddit'] = test_reddit()
    results['youtube'] = test_youtube()

    # Twitter test (disabled by default)
    results['twitter'] = test_twitter()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Results Summary")
    logger.info("=" * 60)

    for platform, result in results.items():
        if result is True:
            status = "✓ PASS"
        elif result is False:
            status = "✗ FAIL"
        else:
            status = "⊘ SKIPPED"

        logger.info(f"{platform:15s}: {status}")

    # Rate limiter status
    logger.info("\n" + "=" * 60)
    logger.info("Rate Limiter Status")
    logger.info("=" * 60)
    rate_limiter = get_rate_limiter()
    rate_limiter.print_status()

    # Final recommendations
    logger.info("\n" + "=" * 60)
    logger.info("Next Steps")
    logger.info("=" * 60)

    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)

    if passed > 0:
        logger.info(f"✓ {passed} platform(s) working correctly")

    if failed > 0:
        logger.info(f"✗ {failed} platform(s) need API configuration")
        logger.info("  See WESTERN_MEDIA_SETUP.md for API setup instructions")

    logger.info("\nFor detailed usage examples, see WESTERN_MEDIA_SETUP.md")
    logger.info("Remember to use conservative rate limits to protect your IP!")


if __name__ == "__main__":
    asyncio.run(main())
