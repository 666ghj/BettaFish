# -*- coding: utf-8 -*-
"""
通用备忘条目模型。

所有待办/提醒的通用抽象，各模块（F1/F4/F7）的提醒统一走 memo_item 调度。
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Enum as SAEnum, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class MemoItem(Base):
    __tablename__ = "memo_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="备忘内容(自然语言原文)")
    category: Mapped[str] = mapped_column(
        SAEnum(
            "financial", "shopping", "vehicle", "health", "anniversary",
            "social", "document", "other",
            name="memo_category",
        ),
        default="other",
        comment="分类",
    )
    due_time: Mapped[datetime] = mapped_column(DateTime, nullable=True, comment="到期时间")
    repeat_rule: Mapped[dict] = mapped_column(JSON, nullable=True, comment="重复规则")
    assignee_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="负责人member_id")
    creator_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="创建人member_id")
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "done", "cancelled", name="memo_status"),
        default="pending",
    )
    source_type: Mapped[str] = mapped_column(
        SAEnum("chat", "manual", name="memo_source"),
        default="chat",
    )
    biz_type: Mapped[str] = mapped_column(String(50), nullable=True, comment="业务类型: payment/vehicle/anniversary等")
    biz_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="业务记录ID")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )