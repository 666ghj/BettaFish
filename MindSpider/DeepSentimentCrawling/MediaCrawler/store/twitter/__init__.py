# -*- coding: utf-8 -*-
"""
Twitter/X store implementation.

Provides storage implementations for Twitter content, comments, and users.
"""

from typing import Dict, List

import config
from var import source_keyword_var
from tools import utils

from ._store_impl import (
    TwitterCsvStoreImplement,
    TwitterDbStoreImplement,
    TwitterJsonStoreImplement,
    TwitterSqliteStoreImplement,
)
from base.base_crawler import AbstractStore


class TwitterStoreFactory:
    """Factory for creating Twitter store implementations."""
    STORES = {
        "csv": TwitterCsvStoreImplement,
        "db": TwitterDbStoreImplement,
        "json": TwitterJsonStoreImplement,
        "sqlite": TwitterSqliteStoreImplement,
        "postgresql": TwitterDbStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = TwitterStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                "[TwitterStoreFactory.create_store] Invalid save option. "
                "Only supported: csv, db, json, sqlite, postgresql"
            )
        return store_class()


async def update_twitter_content(tweet_item: Dict):
    """
    Store or update a Twitter tweet.

    Args:
        tweet_item: Tweet data dictionary with fields:
            - tweet_id: Tweet ID
            - user_id: Author user ID
            - username: Author username (screen_name)
            - display_name: Author display name
            - avatar: Author avatar URL
            - content: Tweet text content
            - created_at: Creation timestamp
            - retweet_count, like_count, reply_count, quote_count, view_count
            - tweet_url: Full tweet URL
            - media_urls: JSON string of media URLs
            - hashtags: JSON string of hashtags
            - language: Tweet language code
    """
    save_content_item = {
        "tweet_id": str(tweet_item.get("id") or tweet_item.get("tweet_id")),
        "user_id": str(tweet_item.get("author_id") or tweet_item.get("user_id")),
        "username": tweet_item.get("author") or tweet_item.get("username"),
        "display_name": tweet_item.get("author_name") or tweet_item.get("display_name"),
        "avatar": tweet_item.get("avatar", ""),
        "content": tweet_item.get("content", ""),
        "created_at": tweet_item.get("created_at"),
        "retweet_count": int(tweet_item.get("retweet_count", 0) or 0),
        "like_count": int(tweet_item.get("like_count", 0) or 0),
        "reply_count": int(tweet_item.get("reply_count", 0) or 0),
        "quote_count": int(tweet_item.get("quote_count", 0) or 0),
        "view_count": int(tweet_item.get("view_count", 0) or 0),
        "tweet_url": tweet_item.get("url") or tweet_item.get("tweet_url"),
        "media_urls": tweet_item.get("media_urls", ""),
        "hashtags": tweet_item.get("hashtags", ""),
        "language": tweet_item.get("language"),
        "source_keyword": source_keyword_var.get() if source_keyword_var.get() else "",
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(
        f"[store.twitter.update_twitter_content] tweet_id: {save_content_item['tweet_id']}, "
        f"author: {save_content_item['username']}"
    )
    await TwitterStoreFactory.create_store().store_content(content_item=save_content_item)


async def update_twitter_comment(tweet_id: str, comment_item: Dict):
    """
    Store or update a Twitter reply/comment.

    Args:
        tweet_id: Parent tweet ID
        comment_item: Reply data dictionary
    """
    save_comment_item = {
        "comment_id": str(comment_item.get("id") or comment_item.get("comment_id")),
        "tweet_id": str(tweet_id),
        "user_id": str(comment_item.get("author_id") or comment_item.get("user_id")),
        "username": comment_item.get("author") or comment_item.get("username"),
        "display_name": comment_item.get("author_name") or comment_item.get("display_name"),
        "avatar": comment_item.get("avatar", ""),
        "content": comment_item.get("content", ""),
        "created_at": comment_item.get("created_at"),
        "like_count": int(comment_item.get("like_count", 0) or 0),
        "reply_count": int(comment_item.get("reply_count", 0) or 0),
        "parent_comment_id": comment_item.get("parent_id") or comment_item.get("parent_comment_id"),
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(
        f"[store.twitter.update_twitter_comment] comment_id: {save_comment_item['comment_id']}, "
        f"tweet_id: {tweet_id}"
    )
    await TwitterStoreFactory.create_store().store_comment(comment_item=save_comment_item)


async def batch_update_twitter_comments(tweet_id: str, comments: List[Dict]):
    """Batch store Twitter replies."""
    if not comments:
        return
    for comment_item in comments:
        await update_twitter_comment(tweet_id, comment_item)


async def update_twitter_user(user_item: Dict):
    """
    Store or update a Twitter user profile.

    Args:
        user_item: User data dictionary
    """
    save_user_item = {
        "user_id": str(user_item.get("id") or user_item.get("user_id")),
        "username": user_item.get("screen_name") or user_item.get("username"),
        "display_name": user_item.get("name") or user_item.get("display_name"),
        "avatar": user_item.get("profile_image_url") or user_item.get("avatar"),
        "bio": user_item.get("description") or user_item.get("bio"),
        "location": user_item.get("location"),
        "website": user_item.get("url") or user_item.get("website"),
        "created_at": user_item.get("created_at"),
        "followers_count": int(user_item.get("followers_count", 0) or 0),
        "following_count": int(user_item.get("friends_count") or user_item.get("following_count", 0) or 0),
        "tweet_count": int(user_item.get("statuses_count") or user_item.get("tweet_count", 0) or 0),
        "verified": 1 if user_item.get("verified") else 0,
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(
        f"[store.twitter.update_twitter_user] user_id: {save_user_item['user_id']}, "
        f"username: {save_user_item['username']}"
    )
    await TwitterStoreFactory.create_store().store_creator(creator=save_user_item)
