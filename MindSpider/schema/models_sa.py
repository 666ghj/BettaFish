"""
MindSpider 数据库ORM模型（SQLAlchemy 2.x）

此模块定义 MindSpider 扩展表（与原 MediaCrawler 表解耦）的 ORM 模型。
数据模型定义位置：
- 本文件（MindSpider/schema/models_sa.py）
"""

from __future__ import annotations

from typing import Optional
from datetime import date

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, BigInteger, Date, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.schema import ForeignKeyConstraint
from sqlalchemy.orm import relationship
__all__ = [
    "Base",
    "DailyNews",
    "DailyTopic",
    "TopicNewsRelation",
    "CrawlingTask",
]


class Base(DeclarativeBase):
    pass


class DailyNews(Base):
    __tablename__ = "daily_news"
    __table_args__ = (
        UniqueConstraint("news_id", name="uq_daily_news_id_unique"),  # 为外键引用添加唯一约束
        UniqueConstraint("news_id", "source_platform", "crawl_date", name="uq_daily_news_unique"),
        Index("idx_daily_news_date", "crawl_date"),
        Index("idx_daily_news_platform", "source_platform"),
        Index("idx_daily_news_rank", "rank_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(512))
    description: Mapped[Optional[str]] = mapped_column(Text)
    extra_info: Mapped[Optional[str]] = mapped_column(Text)
    crawl_date: Mapped[date] = mapped_column(Date, nullable=False)
    rank_position: Mapped[Optional[int]] = mapped_column(Integer)
    add_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_modify_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)


class DailyTopic(Base):
    __tablename__ = "daily_topics"
    __table_args__ = (
        UniqueConstraint("topic_id", name="uq_daily_topics_id_unique"),  # 为外键引用添加唯一约束
        UniqueConstraint("topic_id", "extract_date", name="uq_daily_topics_unique"),
        Index("idx_daily_topics_date", "extract_date"),
        Index("idx_daily_topics_status", "processing_status"),
        Index("idx_daily_topics_score", "relevance_score"),
        Index("idx_topic_date_status", "extract_date", "processing_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_description: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[str]] = mapped_column(Text)
    extract_date: Mapped[date] = mapped_column(Date, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    news_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    processing_status: Mapped[Optional[str]] = mapped_column(String(16), default="pending")
    add_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_modify_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)


class TopicNewsRelation(Base):
    __tablename__ = "topic_news_relation"
    __table_args__ = (
        UniqueConstraint("topic_id", "news_id", "extract_date", name="uq_topic_news_unique"),
        Index("idx_topic_news_topic", "topic_id"),
        Index("idx_topic_news_news", "news_id"),
        Index("idx_topic_news_date", "extract_date"),
        ForeignKeyConstraint(["topic_id"], ["daily_topics.topic_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["news_id"], ["daily_news.news_id"], ondelete="CASCADE"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)
    news_id: Mapped[str] = mapped_column(String(128), nullable=False)
    relation_score: Mapped[Optional[float]] = mapped_column(Float)
    extract_date: Mapped[date] = mapped_column(Date, nullable=False)
    add_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)


class CrawlingTask(Base):
    __tablename__ = "crawling_tasks"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_crawling_tasks_unique"),
        Index("idx_crawling_tasks_topic", "topic_id"),
        Index("idx_crawling_tasks_platform", "platform"),
        Index("idx_crawling_tasks_status", "task_status"),
        Index("idx_crawling_tasks_date", "scheduled_date"),
        Index("idx_task_topic_platform", "topic_id", "platform", "task_status"),
        ForeignKeyConstraint(["topic_id"], ["daily_topics.topic_id"], ondelete="CASCADE"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    search_keywords: Mapped[str] = mapped_column(Text, nullable=False)
    task_status: Mapped[Optional[str]] = mapped_column(String(16), default="pending")
    start_time: Mapped[Optional[int]] = mapped_column(BigInteger)
    end_time: Mapped[Optional[int]] = mapped_column(BigInteger)
    total_crawled: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    success_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    error_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    config_params: Mapped[Optional[str]] = mapped_column(Text)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    add_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_modify_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)


