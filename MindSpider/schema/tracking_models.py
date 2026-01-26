"""
Topic Tracking Models - Continuous monitoring of topics over time

This module provides database models for tracking topics across multiple days,
storing sentiment snapshots, and enabling trend analysis with visualization.
"""

from __future__ import annotations

from typing import Optional
from datetime import date, datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Text, BigInteger, Date, DateTime, Float, JSON, Index, UniqueConstraint
from sqlalchemy.schema import ForeignKeyConstraint

from .models_sa import Base

__all__ = [
    "TopicTrackingSession",
    "SentimentSnapshot",
    "OpinionShiftEvent",
]


class TopicTrackingSession(Base):
    """
    Tracks a continuous monitoring session for a specific topic.
    Each session monitors a topic over a defined time period.
    """
    __tablename__ = "topic_tracking_sessions"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_tracking_session_unique"),
        Index("idx_tracking_session_topic", "topic_name"),
        Index("idx_tracking_session_status", "status"),
        Index("idx_tracking_session_dates", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_name: Mapped[str] = mapped_column(String(500), nullable=False)
    topic_keywords: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of keywords

    # Tracking configuration
    platforms_monitored: Mapped[Optional[str]] = mapped_column(Text)  # JSON array: ["weibo", "xhs", "douyin"]
    monitoring_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)

    # Time range
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_hours: Mapped[Optional[float]] = mapped_column(Float)

    # Aggregated metrics
    total_snapshots: Mapped[int] = mapped_column(Integer, default=0)
    total_articles_tracked: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    sentiment_volatility: Mapped[Optional[float]] = mapped_column(Float)  # Standard deviation

    # Trend summary
    initial_sentiment: Mapped[Optional[float]] = mapped_column(Float)
    final_sentiment: Mapped[Optional[float]] = mapped_column(Float)
    sentiment_change: Mapped[Optional[float]] = mapped_column(Float)
    trend_direction: Mapped[Optional[str]] = mapped_column(String(32))  # "increasing", "stable", "decreasing"

    # Status
    status: Mapped[str] = mapped_column(String(16), default="active")  # active, paused, completed, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    config_params: Mapped[Optional[str]] = mapped_column(Text)  # JSON config
    add_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_modify_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)


class SentimentSnapshot(Base):
    """
    A point-in-time snapshot of sentiment for a tracked topic.
    These form the time series for trend visualization.
    """
    __tablename__ = "sentiment_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_id", name="uq_snapshot_unique"),
        Index("idx_snapshot_session", "session_id"),
        Index("idx_snapshot_time", "snapshot_time"),
        Index("idx_snapshot_session_time", "session_id", "snapshot_time"),
        ForeignKeyConstraint(
            ["session_id"],
            ["topic_tracking_sessions.session_id"],
            ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Timestamp
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Order within session

    # Sentiment metrics
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)  # -1.0 to 1.0
    sentiment_label: Mapped[str] = mapped_column(String(32), nullable=False)  # very_negative to very_positive
    confidence: Mapped[Optional[float]] = mapped_column(Float)

    # Volume metrics
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    positive_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)

    # Change from previous
    sentiment_change: Mapped[Optional[float]] = mapped_column(Float)
    volume_change_pct: Mapped[Optional[float]] = mapped_column(Float)

    # Platform breakdown (JSON)
    platform_breakdown: Mapped[Optional[str]] = mapped_column(Text)  # {"weibo": 0.3, "xhs": -0.1, ...}

    # Key content
    top_positive_content: Mapped[Optional[str]] = mapped_column(Text)  # JSON array
    top_negative_content: Mapped[Optional[str]] = mapped_column(Text)  # JSON array
    trending_keywords: Mapped[Optional[str]] = mapped_column(Text)  # JSON array

    # Raw data reference
    raw_data_path: Mapped[Optional[str]] = mapped_column(String(512))

    add_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)


class OpinionShiftEvent(Base):
    """
    Records significant shifts in public opinion during tracking.
    Used to highlight key moments in the timeline visualization.
    """
    __tablename__ = "opinion_shift_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_shift_event_unique"),
        Index("idx_shift_session", "session_id"),
        Index("idx_shift_time", "event_time"),
        Index("idx_shift_magnitude", "magnitude"),
        ForeignKeyConstraint(
            ["session_id"],
            ["topic_tracking_sessions.session_id"],
            ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Event timing
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Shift metrics
    before_sentiment: Mapped[float] = mapped_column(Float, nullable=False)
    after_sentiment: Mapped[float] = mapped_column(Float, nullable=False)
    magnitude: Mapped[float] = mapped_column(Float, nullable=False)  # Absolute change
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # "positive" or "negative"

    # Event details
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)  # breaking_news, viral_post, official_statement
    trigger_content: Mapped[Optional[str]] = mapped_column(Text)  # Content that triggered the shift
    trigger_source: Mapped[Optional[str]] = mapped_column(String(128))  # Platform/source
    trigger_url: Mapped[Optional[str]] = mapped_column(String(512))

    # Impact assessment
    sustained: Mapped[Optional[bool]] = mapped_column(default=True)  # Did the shift persist?
    reversal_time: Mapped[Optional[datetime]] = mapped_column(DateTime)  # When did it reverse (if any)

    # Description
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    add_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)


# Helper functions for creating instances
def create_tracking_session(
    topic_name: str,
    platforms: list[str] = None,
    duration_hours: float = 24,
    interval_minutes: int = 60
) -> dict:
    """Create configuration for a new tracking session."""
    import uuid
    import time
    import json

    now = datetime.now()
    return {
        "session_id": f"track_{uuid.uuid4().hex[:12]}",
        "topic_name": topic_name,
        "platforms_monitored": json.dumps(platforms or ["weibo", "xhs", "douyin"]),
        "monitoring_interval_minutes": interval_minutes,
        "start_date": now,
        "duration_hours": duration_hours,
        "status": "active",
        "add_ts": int(time.time() * 1000),
        "last_modify_ts": int(time.time() * 1000)
    }


def create_sentiment_snapshot(
    session_id: str,
    sequence: int,
    sentiment_score: float,
    article_count: int,
    positive: int,
    negative: int,
    neutral: int,
    previous_score: float = None
) -> dict:
    """Create a new sentiment snapshot."""
    import uuid
    import time

    labels = {
        (-1.0, -0.6): "very_negative",
        (-0.6, -0.2): "negative",
        (-0.2, 0.2): "neutral",
        (0.2, 0.6): "positive",
        (0.6, 1.0): "very_positive"
    }

    label = "neutral"
    for (low, high), lbl in labels.items():
        if low <= sentiment_score < high:
            label = lbl
            break

    change = None
    if previous_score is not None:
        change = sentiment_score - previous_score

    return {
        "snapshot_id": f"snap_{uuid.uuid4().hex[:12]}",
        "session_id": session_id,
        "snapshot_time": datetime.now(),
        "sequence_number": sequence,
        "sentiment_score": sentiment_score,
        "sentiment_label": label,
        "article_count": article_count,
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "sentiment_change": change,
        "add_ts": int(time.time() * 1000)
    }
