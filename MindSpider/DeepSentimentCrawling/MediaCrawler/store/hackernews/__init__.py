# -*- coding: utf-8 -*-
"""
HackerNews store implementation.

Provides storage implementations for HackerNews stories, comments, and users.
"""

from typing import Dict, List

import config
from var import source_keyword_var
from tools import utils

from ._store_impl import (
    HackerNewsCsvStoreImplement,
    HackerNewsDbStoreImplement,
    HackerNewsJsonStoreImplement,
    HackerNewsSqliteStoreImplement,
)
from base.base_crawler import AbstractStore


class HackerNewsStoreFactory:
    """Factory for creating HackerNews store implementations."""
    STORES = {
        "csv": HackerNewsCsvStoreImplement,
        "db": HackerNewsDbStoreImplement,
        "json": HackerNewsJsonStoreImplement,
        "sqlite": HackerNewsSqliteStoreImplement,
        "postgresql": HackerNewsDbStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = HackerNewsStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                "[HackerNewsStoreFactory.create_store] Invalid save option. "
                "Only supported: csv, db, json, sqlite, postgresql"
            )
        return store_class()


async def update_hackernews_content(story_item: Dict):
    """
    Store or update a HackerNews story.

    Args:
        story_item: Story data dictionary with fields:
            - item_id: HackerNews item ID
            - item_type: 'story', 'job', 'poll', etc.
            - author: Author username (by)
            - title: Story title
            - url: External URL (if link post)
            - text: Story text (if Ask HN, etc.)
            - created_at: Creation timestamp
            - points: Score/points
            - num_comments: Number of descendants (comments)
            - story_url: HackerNews URL
    """
    save_content_item = {
        "item_id": int(story_item.get("id") or story_item.get("item_id")),
        "item_type": story_item.get("type") or story_item.get("item_type", "story"),
        "author": story_item.get("by") or story_item.get("author", ""),
        "title": story_item.get("title", ""),
        "url": story_item.get("url", ""),
        "text": story_item.get("text") or story_item.get("content", ""),
        "created_at": story_item.get("time") or story_item.get("created_at"),
        "points": int(story_item.get("score") or story_item.get("points", 0) or 0),
        "num_comments": int(story_item.get("descendants") or story_item.get("num_comments", 0) or 0),
        "story_url": story_item.get("story_url") or f"https://news.ycombinator.com/item?id={story_item.get('id') or story_item.get('item_id')}",
        "source_keyword": source_keyword_var.get() if source_keyword_var.get() else "",
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(
        f"[store.hackernews.update_hackernews_content] item_id: {save_content_item['item_id']}, "
        f"title: {save_content_item['title'][:50]}..."
    )
    await HackerNewsStoreFactory.create_store().store_content(content_item=save_content_item)


async def update_hackernews_comment(story_id: int, comment_item: Dict):
    """
    Store or update a HackerNews comment.

    Args:
        story_id: Parent story ID
        comment_item: Comment data dictionary
    """
    save_comment_item = {
        "comment_id": int(comment_item.get("id") or comment_item.get("comment_id")),
        "story_id": int(story_id),
        "author": comment_item.get("by") or comment_item.get("author", ""),
        "text": comment_item.get("text") or comment_item.get("content", ""),
        "created_at": comment_item.get("time") or comment_item.get("created_at"),
        "parent_id": int(comment_item.get("parent") or comment_item.get("parent_id") or story_id),
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(
        f"[store.hackernews.update_hackernews_comment] comment_id: {save_comment_item['comment_id']}, "
        f"story_id: {story_id}"
    )
    await HackerNewsStoreFactory.create_store().store_comment(comment_item=save_comment_item)


async def batch_update_hackernews_comments(story_id: int, comments: List[Dict]):
    """Batch store HackerNews comments."""
    if not comments:
        return
    for comment_item in comments:
        await update_hackernews_comment(story_id, comment_item)
