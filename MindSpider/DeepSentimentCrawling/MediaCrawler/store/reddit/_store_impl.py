# -*- coding: utf-8 -*-
"""
Reddit store implementations for CSV, DB, JSON, and SQLite.
"""

from typing import Dict

from sqlalchemy import select

from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import RedditContent, RedditComment, RedditUser
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


class RedditCsvStoreImplement(AbstractStore):
    """CSV storage implementation for Reddit."""

    def __init__(self):
        self.file_writer = AsyncFileWriter(
            crawler_type=crawler_type_var.get(),
            platform="reddit"
        )

    async def store_content(self, content_item: Dict):
        await self.file_writer.write_to_csv(
            item=content_item,
            item_type="posts"
        )

    async def store_comment(self, comment_item: Dict):
        await self.file_writer.write_to_csv(
            item=comment_item,
            item_type="comments"
        )

    async def store_creator(self, creator: Dict):
        await self.file_writer.write_to_csv(
            item=creator,
            item_type="users"
        )


class RedditDbStoreImplement(AbstractStore):
    """Database storage implementation for Reddit (PostgreSQL/MySQL)."""

    async def store_content(self, content_item: Dict):
        """Store Reddit post to database."""
        post_id = content_item.get("post_id")
        content_item = _sanitize_strings(content_item)

        async with get_session() as session:
            result = await session.execute(
                select(RedditContent).where(RedditContent.post_id == post_id)
            )
            post_detail = result.scalar_one_or_none()

            if not post_detail:
                content_item["add_ts"] = utils.get_current_timestamp()
                new_content = RedditContent(**content_item)
                session.add(new_content)
            else:
                for key, value in content_item.items():
                    setattr(post_detail, key, value)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """Store Reddit comment to database."""
        comment_id = comment_item.get("comment_id")
        comment_item = _sanitize_strings(comment_item)

        async with get_session() as session:
            result = await session.execute(
                select(RedditComment).where(RedditComment.comment_id == comment_id)
            )
            comment_detail = result.scalar_one_or_none()

            if not comment_detail:
                comment_item["add_ts"] = utils.get_current_timestamp()
                new_comment = RedditComment(**comment_item)
                session.add(new_comment)
            else:
                for key, value in comment_item.items():
                    setattr(comment_detail, key, value)
            await session.commit()

    async def store_creator(self, creator: Dict):
        """Store Reddit user to database."""
        user_id = creator.get("user_id")
        creator = _sanitize_strings(creator)

        async with get_session() as session:
            result = await session.execute(
                select(RedditUser).where(RedditUser.user_id == user_id)
            )
            user_detail = result.scalar_one_or_none()

            if not user_detail:
                creator["add_ts"] = utils.get_current_timestamp()
                new_user = RedditUser(**creator)
                session.add(new_user)
            else:
                for key, value in creator.items():
                    setattr(user_detail, key, value)
            await session.commit()


class RedditJsonStoreImplement(AbstractStore):
    """JSON storage implementation for Reddit."""

    def __init__(self):
        self.file_writer = AsyncFileWriter(
            crawler_type=crawler_type_var.get(),
            platform="reddit"
        )

    async def store_content(self, content_item: Dict):
        await self.file_writer.write_single_item_to_json(
            item=content_item,
            item_type="posts"
        )

    async def store_comment(self, comment_item: Dict):
        await self.file_writer.write_single_item_to_json(
            item=comment_item,
            item_type="comments"
        )

    async def store_creator(self, creator: Dict):
        await self.file_writer.write_single_item_to_json(
            item=creator,
            item_type="users"
        )


class RedditSqliteStoreImplement(RedditDbStoreImplement):
    """SQLite storage implementation (same as DB implementation)."""
    pass
