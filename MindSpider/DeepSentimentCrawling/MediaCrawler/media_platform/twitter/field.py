"""
Twitter data field definitions and mappings.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TwitterTweet:
    """Standardized tweet data structure."""
    id: str
    content: str
    author: str
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    created_at: Optional[str] = None
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    view_count: int = 0
    language: Optional[str] = None
    url: Optional[str] = None
    parent_id: Optional[str] = None  # For replies
    collected_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "platform": "twitter",
            "content": self.content,
            "author": self.author,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "created_at": self.created_at,
            "retweet_count": self.retweet_count,
            "like_count": self.like_count,
            "reply_count": self.reply_count,
            "quote_count": self.quote_count,
            "view_count": self.view_count,
            "language": self.language,
            "url": self.url,
            "parent_id": self.parent_id,
            "collected_at": self.collected_at or datetime.now().isoformat(),
        }


# Field mapping from twikit to our schema
TWIKIT_FIELD_MAP = {
    "id": "id",
    "text": "content",
    "user.screen_name": "author",
    "user.id": "author_id",
    "user.name": "author_name",
    "created_at": "created_at",
    "retweet_count": "retweet_count",
    "favorite_count": "like_count",
    "reply_count": "reply_count",
    "quote_count": "quote_count",
    "view_count": "view_count",
    "lang": "language",
}
