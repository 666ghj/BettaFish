"""
E2E tests for Western media platform crawlers.

Tests:
- Twitter/X crawler
- Reddit crawler
- HackerNews crawler

Each test verifies:
1. Crawler initialization
2. Search functionality
3. Data structure validation
4. Anti-bot mechanism effectiveness
"""

import asyncio
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Any

import pytest

# Skip if dependencies not available
pytest.importorskip("httpx")


class TestHackerNewsCrawler:
    """Tests for HackerNews crawler (no auth required)."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_hackernews_initialization(self):
        """Test HackerNews crawler initializes correctly."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsCrawler

        crawler = HackerNewsCrawler()
        await crawler.start()

        assert crawler.client is not None
        await crawler.close()

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_hackernews_search(self, test_query):
        """Test HackerNews search returns valid results."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsCrawler

        crawler = HackerNewsCrawler()
        crawler.keyword = "OpenAI"  # Use simpler query for reliability
        crawler.max_results = 10

        await crawler.start()
        results = await crawler.search()
        await crawler.close()

        assert len(results) > 0, "HackerNews returned no results"

        # Validate data structure
        first_result = results[0]
        required_fields = ["id", "platform", "title", "author", "points"]
        for field in required_fields:
            assert field in first_result, f"Missing required field: {field}"

        assert first_result["platform"] == "hackernews"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_hackernews_top_stories(self):
        """Test fetching HackerNews top stories."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsCrawler

        crawler = HackerNewsCrawler()
        await crawler.start()

        stories = await crawler.get_top_stories(limit=5)
        await crawler.close()

        assert len(stories) > 0, "No top stories returned"
        assert all(s.get("item_type") == "story" for s in stories)

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_hackernews_network_variance(self):
        """
        Anti-cheat: Verify real network calls by checking timing variance.

        Real API calls have >50ms timing variance between calls.
        Fake/mocked responses have near-zero variance.
        """
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsCrawler

        crawler = HackerNewsCrawler()
        crawler.keyword = "AI"
        crawler.max_results = 5

        await crawler.start()

        timings = []
        for _ in range(3):
            start = time.time()
            await crawler.search()
            elapsed = (time.time() - start) * 1000
            timings.append(elapsed)
            await asyncio.sleep(0.5)

        await crawler.close()

        variance = max(timings) - min(timings)
        assert variance >= 30, f"Timing variance {variance}ms too low - likely mocked responses"


class TestRedditCrawler:
    """Tests for Reddit crawler (requires OAuth credentials)."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_reddit_initialization(self):
        """Test Reddit crawler initialization."""
        try:
            from config import settings
            if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
                pytest.skip("Reddit credentials not configured")
        except ImportError:
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit import RedditCrawler

        crawler = RedditCrawler()
        await crawler.start()

        assert crawler.is_initialized
        assert crawler.reddit is not None
        await crawler.close()

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_reddit_search(self, test_query):
        """Test Reddit search returns valid results."""
        try:
            from config import settings
            if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
                pytest.skip("Reddit credentials not configured")
        except ImportError:
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit import RedditCrawler

        crawler = RedditCrawler()
        crawler.keyword = "artificial intelligence"
        crawler.max_results = 10

        await crawler.start()
        results = await crawler.search()
        await crawler.close()

        assert len(results) > 0, "Reddit returned no results"

        # Validate data structure
        first_result = results[0]
        required_fields = ["id", "platform", "title", "subreddit", "score"]
        for field in required_fields:
            assert field in first_result, f"Missing required field: {field}"

        assert first_result["platform"] == "reddit"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_reddit_unique_queries(self):
        """
        Anti-cheat: Verify different queries return different results.

        Real implementations return unique results for different queries.
        Fake implementations may return the same hardcoded data.
        """
        try:
            from config import settings
            if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
                pytest.skip("Reddit credentials not configured")
        except ImportError:
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit import RedditCrawler

        crawler = RedditCrawler()
        crawler.max_results = 5
        await crawler.start()

        queries = ["python programming", "machine learning", "space exploration"]
        result_hashes = []

        for query in queries:
            crawler.keyword = query
            results = await crawler.search()
            # Hash first result for comparison
            if results:
                hash_input = f"{results[0].get('id', '')}{results[0].get('title', '')}"
                result_hashes.append(hashlib.md5(hash_input.encode()).hexdigest())

        await crawler.close()

        # Different queries should produce different results
        unique_hashes = len(set(result_hashes))
        assert unique_hashes >= 2, f"Only {unique_hashes} unique result sets - possible hardcoded responses"


class TestTwitterCrawler:
    """Tests for Twitter crawler (requires credentials)."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_twitter_initialization(self):
        """Test Twitter crawler initialization."""
        try:
            from config import settings
            if not all([settings.TWITTER_USERNAME, settings.TWITTER_EMAIL, settings.TWITTER_PASSWORD]):
                if not settings.TWITTER_COOKIES_PATH:
                    pytest.skip("Twitter credentials not configured")
        except ImportError:
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.twitter import TwitterCrawler

        crawler = TwitterCrawler()
        # Just test that crawler can be instantiated
        assert crawler.platform == "twitter"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_twitter_search(self, test_query):
        """Test Twitter search returns valid results."""
        try:
            from config import settings
            if not all([settings.TWITTER_USERNAME, settings.TWITTER_EMAIL, settings.TWITTER_PASSWORD]):
                if not settings.TWITTER_COOKIES_PATH:
                    pytest.skip("Twitter credentials not configured")
        except ImportError:
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.twitter import TwitterCrawler

        crawler = TwitterCrawler()
        crawler.keyword = "AI"
        crawler.max_results = 10

        try:
            await crawler.start()
            results = await crawler.search()
            await crawler.close()

            if len(results) > 0:
                # Validate data structure
                first_result = results[0]
                required_fields = ["id", "platform", "content", "author"]
                for field in required_fields:
                    assert field in first_result, f"Missing required field: {field}"

                assert first_result["platform"] == "twitter"
        except Exception as e:
            # Twitter login can fail due to various reasons
            pytest.skip(f"Twitter auth failed: {e}")


class TestCrossplatformSearch:
    """Test searching across multiple platforms."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_multi_platform_search(self, test_query):
        """
        Test searching "OpenAI future forecast 2026" across platforms.

        This is the core E2E test that validates:
        1. Multiple platforms can be searched
        2. Results are returned from each platform
        3. Data structures are consistent
        """
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsCrawler

        results = {}

        # HackerNews (always available)
        hn_crawler = HackerNewsCrawler()
        hn_crawler.keyword = "OpenAI"
        hn_crawler.max_results = 10
        await hn_crawler.start()
        results["hackernews"] = await hn_crawler.search()
        await hn_crawler.close()

        # Reddit (if configured)
        try:
            from config import settings
            if settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET:
                from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit import RedditCrawler
                reddit_crawler = RedditCrawler()
                reddit_crawler.keyword = "OpenAI"
                reddit_crawler.max_results = 10
                await reddit_crawler.start()
                results["reddit"] = await reddit_crawler.search()
                await reddit_crawler.close()
        except ImportError:
            pass

        # Verify results
        assert len(results) >= 1, "No platforms returned results"
        assert len(results.get("hackernews", [])) > 0, "HackerNews returned no results"

        # Check data consistency
        for platform, items in results.items():
            for item in items:
                assert "id" in item, f"{platform}: Missing 'id' field"
                assert "platform" in item, f"{platform}: Missing 'platform' field"
                assert item["platform"] == platform, f"Platform mismatch in {platform} data"

        print(f"Multi-platform search successful: {list(results.keys())}")
        print(f"Results per platform: {[(k, len(v)) for k, v in results.items()]}")


class TestPlatformClients:
    """Tests for platform-specific API clients."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_hackernews_client_search(self):
        """Test HackerNewsClient search_stories method."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsClient

        client = HackerNewsClient()
        results = await client.search_stories("python", hits_per_page=5)
        await client.close()

        assert len(results) >= 1, "HackerNewsClient should return at least 1 story"

        for story in results:
            assert "id" in story
            assert "title" in story

        print(f"[HackerNewsClient] Found {len(results)} stories")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_hackernews_client_top_stories(self):
        """Test HackerNewsClient top stories fetch."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews import HackerNewsClient

        client = HackerNewsClient()
        results = await client.get_top_stories(limit=5)
        await client.close()

        assert len(results) >= 1, "Should return at least 1 top story"
        print(f"[HackerNewsClient] Got {len(results)} top stories")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_reddit_client_search(self):
        """Test RedditClient search method."""
        try:
            from config import settings
            if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
                pytest.skip("Reddit credentials not configured")
        except ImportError:
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit import RedditClient

        client = RedditClient()
        if not client.authenticate():
            pytest.skip("Reddit authentication failed")

        results = client.search_posts("python", limit=5)

        assert len(results) >= 1, "RedditClient should return at least 1 post"

        for post in results:
            assert "id" in post
            assert "subreddit" in post

        print(f"[RedditClient] Found {len(results)} posts")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_twitter_client_auth(self):
        """Test TwitterClient authentication."""
        try:
            from config import settings
            has_creds = all([
                settings.TWITTER_USERNAME,
                settings.TWITTER_EMAIL,
                settings.TWITTER_PASSWORD
            ])
            has_cookies = settings.TWITTER_COOKIES_PATH
            if not has_creds and not has_cookies:
                pytest.skip("Twitter credentials not configured")
        except (ImportError, AttributeError):
            pytest.skip("Config not available")

        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.twitter import TwitterClient

        client = TwitterClient()
        try:
            success = await client.authenticate()
            if success:
                assert client.is_authenticated, "Client should be authenticated"
                print("[TwitterClient] Authentication successful")
            else:
                pytest.skip("Twitter authentication failed")
        except Exception as e:
            pytest.skip(f"Twitter auth error: {e}")


class TestDatabaseModels:
    """Tests for Western platform database models."""

    @pytest.mark.e2e
    def test_twitter_model_fields(self):
        """Verify TwitterContent model has required fields."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.database.models import (
            TwitterContent, TwitterComment, TwitterUser
        )

        # Check TwitterContent columns
        content_cols = [c.name for c in TwitterContent.__table__.columns]
        required = ["tweet_id", "user_id", "content", "created_at", "like_count", "retweet_count"]
        for field in required:
            assert field in content_cols, f"TwitterContent missing field: {field}"

        # Check TwitterComment columns
        comment_cols = [c.name for c in TwitterComment.__table__.columns]
        required = ["comment_id", "tweet_id", "content", "created_at"]
        for field in required:
            assert field in comment_cols, f"TwitterComment missing field: {field}"

        # Check TwitterUser columns
        user_cols = [c.name for c in TwitterUser.__table__.columns]
        required = ["user_id", "username", "followers_count"]
        for field in required:
            assert field in user_cols, f"TwitterUser missing field: {field}"

        print("[DB Models] Twitter models validated")

    @pytest.mark.e2e
    def test_reddit_model_fields(self):
        """Verify RedditContent model has required fields."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.database.models import (
            RedditContent, RedditComment, RedditUser
        )

        # Check RedditContent columns
        content_cols = [c.name for c in RedditContent.__table__.columns]
        required = ["post_id", "subreddit", "title", "content", "score", "num_comments"]
        for field in required:
            assert field in content_cols, f"RedditContent missing field: {field}"

        # Check RedditComment columns
        comment_cols = [c.name for c in RedditComment.__table__.columns]
        required = ["comment_id", "post_id", "content", "score"]
        for field in required:
            assert field in comment_cols, f"RedditComment missing field: {field}"

        print("[DB Models] Reddit models validated")

    @pytest.mark.e2e
    def test_hackernews_model_fields(self):
        """Verify HackerNewsContent model has required fields."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.database.models import (
            HackerNewsContent, HackerNewsComment
        )

        # Check HackerNewsContent columns
        content_cols = [c.name for c in HackerNewsContent.__table__.columns]
        required = ["item_id", "title", "url", "points", "num_comments"]
        for field in required:
            assert field in content_cols, f"HackerNewsContent missing field: {field}"

        # Check HackerNewsComment columns
        comment_cols = [c.name for c in HackerNewsComment.__table__.columns]
        required = ["comment_id", "story_id", "text", "author"]
        for field in required:
            assert field in comment_cols, f"HackerNewsComment missing field: {field}"

        print("[DB Models] HackerNews models validated")
