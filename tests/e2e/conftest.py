"""
E2E test fixtures and configuration.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_twitter_data():
    """Sample Twitter data for testing."""
    return [
        {
            "id": "1234567890123456789",
            "platform": "twitter",
            "content": "OpenAI's 2026 predictions look interesting #AI #future",
            "author": "techanalyst",
            "author_id": "123456",
            "author_name": "Tech Analyst",
            "created_at": "2026-01-15T10:30:00Z",
            "retweet_count": 150,
            "like_count": 500,
            "reply_count": 25,
            "quote_count": 10,
            "view_count": 10000,
            "language": "en",
            "url": "https://twitter.com/techanalyst/status/1234567890123456789",
        }
    ]


@pytest.fixture
def sample_reddit_data():
    """Sample Reddit data for testing."""
    return [
        {
            "id": "abc123xyz",
            "platform": "reddit",
            "title": "OpenAI 2026 Roadmap Discussion",
            "content": "What do you think about OpenAI's future plans and predictions?",
            "author": "ai_enthusiast",
            "subreddit": "MachineLearning",
            "score": 1500,
            "upvote_ratio": 0.95,
            "num_comments": 234,
            "created_at": "2026-01-14T15:00:00Z",
            "url": "https://reddit.com/r/MachineLearning/comments/abc123xyz",
            "is_self": True,
        }
    ]


@pytest.fixture
def sample_hackernews_data():
    """Sample HackerNews data for testing."""
    return [
        {
            "id": "39876543",
            "platform": "hackernews",
            "title": "OpenAI announces 2026 research agenda",
            "content": "",
            "url": "https://openai.com/blog/2026-agenda",
            "author": "sama",
            "points": 2500,
            "num_comments": 450,
            "created_at": "2026-01-13T09:00:00Z",
            "item_type": "story",
            "hn_url": "https://news.ycombinator.com/item?id=39876543",
        }
    ]


@pytest.fixture
def test_query():
    """Test query for E2E tests."""
    return "OpenAI future forecast in 2026"


# Pass criteria for E2E tests
PASS_CRITERIA = {
    "twitter_results": lambda r: len(r) >= 5,
    "reddit_results": lambda r: len(r) >= 5,
    "hackernews_results": lambda r: len(r) >= 3,
    "report_size_bytes": lambda s: s >= 10000,
    "platform_coverage": lambda p: len(p) >= 3,
    "timing_variance_ms": lambda v: v >= 50,
    "unique_response_hashes": lambda h: h >= 2,
}


def check_pass_criteria(name: str, value) -> bool:
    """Check if a value passes the defined criteria."""
    if name in PASS_CRITERIA:
        return PASS_CRITERIA[name](value)
    return True
