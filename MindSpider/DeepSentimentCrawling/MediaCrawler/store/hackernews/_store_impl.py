# -*- coding: utf-8 -*-
"""
HackerNews store implementations for CSV, DB, JSON, and SQLite.
"""

from typing import Dict

from sqlalchemy import select

from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import HackerNewsContent, HackerNewsComment
from tools.async_file_writer import AsyncFileWriter
from tools import utils
from var import crawler_type_var


def _sanitize_strings(data: Dict) -> Dict:
    """
    Remove PostgreSQL-incompatible control characters from all string fields.
    """
    cleaned = {}
    for key, value in data.items():
        if isinstance(value, str):
            cleaned[key] = value.replace('\x00', '')
        else:
            cleaned[key] = value
    return cleaned


class HackerNewsCsvStoreImplement(AbstractStore):
    """CSV storage implementation for HackerNews."""

    def __init__(self):
        self.file_writer = AsyncFileWriter(
            crawler_type=crawler_type_var.get(),
            platform="hackernews"
        )

    async def store_content(self, content_item: Dict):
        await self.file_writer.write_to_csv(
            item=content_item,
            item_type="stories"
        )

    async def store_comment(self, comment_item: Dict):
        await self.file_writer.write_to_csv(
            item=comment_item,
            item_type="comments"
        )

    async def store_creator(self, creator: Dict):
        """HackerNews doesn't have explicit creator storage."""
        pass


class HackerNewsDbStoreImplement(AbstractStore):
    """Database storage implementation for HackerNews (PostgreSQL/MySQL)."""

    async def store_content(self, content_item: Dict):
        """Store HackerNews story to database."""
        item_id = content_item.get("item_id")
        content_item = _sanitize_strings(content_item)

        async with get_session() as session:
            result = await session.execute(
                select(HackerNewsContent).where(HackerNewsContent.item_id == item_id)
            )
            story_detail = result.scalar_one_or_none()

            if not story_detail:
                content_item["add_ts"] = utils.get_current_timestamp()
                new_content = HackerNewsContent(**content_item)
                session.add(new_content)
            else:
                for key, value in content_item.items():
                    setattr(story_detail, key, value)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """Store HackerNews comment to database."""
        comment_id = comment_item.get("comment_id")
        comment_item = _sanitize_strings(comment_item)

        async with get_session() as session:
            result = await session.execute(
                select(HackerNewsComment).where(HackerNewsComment.comment_id == comment_id)
            )
            comment_detail = result.scalar_one_or_none()

            if not comment_detail:
                comment_item["add_ts"] = utils.get_current_timestamp()
                new_comment = HackerNewsComment(**comment_item)
                session.add(new_comment)
            else:
                for key, value in comment_item.items():
                    setattr(comment_detail, key, value)
            await session.commit()

    async def store_creator(self, creator: Dict):
        """HackerNews doesn't have explicit creator storage."""
        pass


class HackerNewsJsonStoreImplement(AbstractStore):
    """JSON storage implementation for HackerNews."""

    def __init__(self):
        self.file_writer = AsyncFileWriter(
            crawler_type=crawler_type_var.get(),
            platform="hackernews"
        )

    async def store_content(self, content_item: Dict):
        await self.file_writer.write_single_item_to_json(
            item=content_item,
            item_type="stories"
        )

    async def store_comment(self, comment_item: Dict):
        await self.file_writer.write_single_item_to_json(
            item=comment_item,
            item_type="comments"
        )

    async def store_creator(self, creator: Dict):
        """HackerNews doesn't have explicit creator storage."""
        pass


class HackerNewsSqliteStoreImplement(HackerNewsDbStoreImplement):
    """SQLite storage implementation (same as DB implementation)."""
    pass
