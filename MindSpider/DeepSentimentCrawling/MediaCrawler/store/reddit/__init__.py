# -*- coding: utf-8 -*-
"""
Reddit store implementation.

Provides storage implementations for Reddit posts, comments, and users.
"""

from typing import Dict, List

import config
from var import source_keyword_var
from tools import utils

from ._store_impl import (
    RedditCsvStoreImplement,
    RedditDbStoreImplement,
    RedditJsonStoreImplement,
    RedditSqliteStoreImplement,
)
from base.base_crawler import AbstractStore


class RedditStoreFactory:
    """Factory for creating Reddit store implementations."""
    STORES = {
        "csv": RedditCsvStoreImplement,
        "db": RedditDbStoreImplement,
        "json": RedditJsonStoreImplement,
        "sqlite": RedditSqliteStoreImplement,
        "postgresql": RedditDbStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = RedditStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                "[RedditStoreFactory.create_store] Invalid save option. "
                "Only supported: csv, db, json, sqlite, postgresql"
            )
        return store_class()


async def update_reddit_content(post_item: Dict):
    """
    Store or update a Reddit post/submission.

    Args:
        post_item: Post data dictionary with fields:
            - post_id: Reddit post ID
            - subreddit: Subreddit name
            - author: Author username
            - author_id: Author ID
            - title: Post title
            - content: Post text (selftext)
            - content_html: HTML content
            - post_url: Full post URL
            - created_at: Creation timestamp
            - score: Upvotes minus downvotes
            - upvote_ratio: Ratio of upvotes
            - num_comments: Number of comments
            - is_self: True if text post
            - is_video: True if video post
            - media_url: Media URL if applicable
            - thumbnail: Thumbnail URL
            - flair: Post flair
            - awards: JSON string of awards
    """
    save_content_item = {
        "post_id": str(post_item.get("id") or post_item.get("post_id")),
        "subreddit": post_item.get("subreddit") or post_item.get("subreddit_name"),
        "author": post_item.get("author") or post_item.get("author_name"),
        "author_id": post_item.get("author_id"),
        "title": post_item.get("title", ""),
        "content": post_item.get("content") or post_item.get("selftext", ""),
        "content_html": post_item.get("content_html") or post_item.get("selftext_html", ""),
        "post_url": post_item.get("url") or post_item.get("post_url"),
        "created_at": post_item.get("created_at") or post_item.get("created_utc"),
        "score": int(post_item.get("score", 0) or 0),
        "upvote_ratio": str(post_item.get("upvote_ratio", "")),
        "num_comments": int(post_item.get("num_comments", 0) or 0),
        "is_self": 1 if post_item.get("is_self") else 0,
        "is_video": 1 if post_item.get("is_video") else 0,
        "media_url": post_item.get("media_url", ""),
        "thumbnail": post_item.get("thumbnail", ""),
        "flair": post_item.get("flair") or post_item.get("link_flair_text", ""),
        "awards": post_item.get("awards", ""),
        "source_keyword": source_keyword_var.get() if source_keyword_var.get() else "",
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(
        f"[store.reddit.update_reddit_content] post_id: {save_content_item['post_id']}, "
        f"subreddit: r/{save_content_item['subreddit']}"
    )
    await RedditStoreFactory.create_store().store_content(content_item=save_content_item)


async def update_reddit_comment(post_id: str, comment_item: Dict):
    """
    Store or update a Reddit comment.

    Args:
        post_id: Parent post ID
        comment_item: Comment data dictionary
    """
    save_comment_item = {
        "comment_id": str(comment_item.get("id") or comment_item.get("comment_id")),
        "post_id": str(post_id),
        "subreddit": comment_item.get("subreddit") or comment_item.get("subreddit_name"),
        "author": comment_item.get("author") or comment_item.get("author_name"),
        "author_id": comment_item.get("author_id"),
        "content": comment_item.get("content") or comment_item.get("body", ""),
        "content_html": comment_item.get("content_html") or comment_item.get("body_html", ""),
        "created_at": comment_item.get("created_at") or comment_item.get("created_utc"),
        "score": int(comment_item.get("score", 0) or 0),
        "parent_comment_id": comment_item.get("parent_id") or comment_item.get("parent_comment_id"),
        "depth": int(comment_item.get("depth", 0) or 0),
        "is_submitter": 1 if comment_item.get("is_submitter") else 0,
        "awards": comment_item.get("awards", ""),
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(
        f"[store.reddit.update_reddit_comment] comment_id: {save_comment_item['comment_id']}, "
        f"post_id: {post_id}"
    )
    await RedditStoreFactory.create_store().store_comment(comment_item=save_comment_item)


async def batch_update_reddit_comments(post_id: str, comments: List[Dict]):
    """Batch store Reddit comments."""
    if not comments:
        return
    for comment_item in comments:
        await update_reddit_comment(post_id, comment_item)


async def update_reddit_user(user_item: Dict):
    """
    Store or update a Reddit user profile.

    Args:
        user_item: User data dictionary
    """
    save_user_item = {
        "user_id": str(user_item.get("id") or user_item.get("user_id")),
        "username": user_item.get("name") or user_item.get("username"),
        "created_at": user_item.get("created_at") or user_item.get("created_utc"),
        "link_karma": int(user_item.get("link_karma", 0) or 0),
        "comment_karma": int(user_item.get("comment_karma", 0) or 0),
        "is_gold": 1 if user_item.get("is_gold") else 0,
        "is_mod": 1 if user_item.get("is_mod") else 0,
        "verified": 1 if user_item.get("verified") or user_item.get("has_verified_email") else 0,
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(
        f"[store.reddit.update_reddit_user] user_id: {save_user_item['user_id']}, "
        f"username: u/{save_user_item['username']}"
    )
    await RedditStoreFactory.create_store().store_creator(creator=save_user_item)
