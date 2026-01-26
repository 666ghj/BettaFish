# -*- coding: utf-8 -*-
"""
Unit tests for Western media platform crawlers.

Tests Twitter, Reddit, and HackerNews clients for:
- Import availability
- Client instantiation
- Basic API functionality (with mocking where needed)
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestHackerNewsClient:
    """Tests for HackerNews client - uses free public API."""

    def test_import(self):
        """Test that HackerNewsClient can be imported."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews.client import (
            HackerNewsClient
        )
        assert HackerNewsClient is not None

    def test_instantiation(self):
        """Test that HackerNewsClient can be instantiated."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews.client import (
            HackerNewsClient
        )
        client = HackerNewsClient()
        assert client is not None
        assert client.ALGOLIA_BASE == "https://hn.algolia.com/api/v1"
        assert client.FIREBASE_BASE == "https://hacker-news.firebaseio.com/v0"

    @pytest.mark.asyncio
    async def test_search_stories_mock(self):
        """Test search_stories with mocked response."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.hackernews.client import (
            HackerNewsClient
        )

        client = HackerNewsClient()

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hits": [
                {
                    "objectID": "12345",
                    "title": "Test Story",
                    "author": "testuser",
                    "url": "https://example.com",
                    "points": 100,
                    "num_comments": 50,
                    "created_at_i": 1700000000,
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            results = await client.search_stories("python", hits_per_page=10)

            assert len(results) == 1
            assert results[0]["title"] == "Test Story"
            assert results[0]["platform"] == "hackernews"

        await client.close()


class TestRedditClient:
    """Tests for Reddit client - requires API credentials."""

    def test_import(self):
        """Test that RedditClient can be imported."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit.client import (
            RedditClient, PRAW_AVAILABLE
        )
        assert RedditClient is not None
        # PRAW should be available if requirements installed
        assert PRAW_AVAILABLE is True

    def test_instantiation_no_credentials(self):
        """Test instantiation without credentials."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit.client import (
            RedditClient
        )
        client = RedditClient()
        assert client is not None
        assert client.is_authenticated is False

    def test_parse_submission_mock(self):
        """Test submission parsing with mock data."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit.client import (
            RedditClient
        )

        client = RedditClient()

        # Create mock submission
        mock_submission = MagicMock()
        mock_submission.id = "abc123"
        mock_submission.title = "Test Post"
        mock_submission.selftext = "Test content"
        mock_submission.selftext_html = "<p>Test content</p>"
        mock_submission.permalink = "/r/test/comments/abc123/test_post"
        mock_submission.created_utc = 1700000000
        mock_submission.score = 100
        mock_submission.upvote_ratio = 0.95
        mock_submission.num_comments = 50
        mock_submission.is_self = True
        mock_submission.is_video = False
        mock_submission.url = "https://reddit.com/r/test"
        mock_submission.thumbnail = "self"
        mock_submission.link_flair_text = "Discussion"
        mock_submission.subreddit = MagicMock()
        mock_submission.subreddit.display_name = "test"
        mock_submission.author = MagicMock()
        mock_submission.author.id = "user123"
        mock_submission.author.__str__ = lambda self: "testuser"

        result = client._parse_submission(mock_submission)

        assert result is not None
        assert result["post_id"] == "abc123"
        assert result["title"] == "Test Post"
        assert result["platform"] == "reddit"
        assert result["subreddit"] == "test"


class TestTwitterClient:
    """Tests for Twitter client - requires authentication."""

    def test_import(self):
        """Test that TwitterClient can be imported."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.twitter.client import (
            TwitterClient, TWIKIT_AVAILABLE
        )
        assert TwitterClient is not None
        # twikit should be available if requirements installed
        assert TWIKIT_AVAILABLE is True

    def test_instantiation(self):
        """Test that TwitterClient can be instantiated."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.twitter.client import (
            TwitterClient
        )
        client = TwitterClient()
        assert client is not None
        assert client.is_authenticated is False

    def test_parse_tweet_mock(self):
        """Test tweet parsing with mock data."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.twitter.client import (
            TwitterClient
        )

        client = TwitterClient()

        # Create mock tweet
        mock_tweet = MagicMock()
        mock_tweet.id = "12345"
        mock_tweet.text = "Test tweet content"
        mock_tweet.created_at = "2024-01-01T00:00:00Z"
        mock_tweet.retweet_count = 10
        mock_tweet.favorite_count = 50
        mock_tweet.reply_count = 5
        mock_tweet.quote_count = 2
        mock_tweet.lang = "en"

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.screen_name = "testuser"
        mock_user.name = "Test User"
        mock_user.profile_image_url = "https://example.com/avatar.jpg"
        mock_tweet.user = mock_user

        result = client._parse_tweet(mock_tweet)

        assert result is not None
        assert result["tweet_id"] == "12345"
        assert result["content"] == "Test tweet content"
        assert result["platform"] == "twitter"
        assert result["username"] == "testuser"


class TestDatabaseModels:
    """Tests for Western platform database models."""

    def test_twitter_models_exist(self):
        """Test that Twitter database models exist."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.database.models import (
            TwitterContent, TwitterComment, TwitterUser
        )
        assert TwitterContent is not None
        assert TwitterComment is not None
        assert TwitterUser is not None

    def test_reddit_models_exist(self):
        """Test that Reddit database models exist."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.database.models import (
            RedditContent, RedditComment, RedditUser
        )
        assert RedditContent is not None
        assert RedditComment is not None
        assert RedditUser is not None

    def test_hackernews_models_exist(self):
        """Test that HackerNews database models exist."""
        from MindSpider.DeepSentimentCrawling.MediaCrawler.database.models import (
            HackerNewsContent, HackerNewsComment
        )
        assert HackerNewsContent is not None
        assert HackerNewsComment is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
