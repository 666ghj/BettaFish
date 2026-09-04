# -*- coding: utf-8 -*-
"""
F7 纪念日/重要日期模型。
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import String, Text, Integer, Enum as SAEnum, DateTime, Date, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Anniversary(Base):
    """纪念日"""
    __tablename__ = "anniversary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="名称")
    date: Mapped[date] = mapped_column(Date, nullable=False, comment="日期")
    reminder_days: Mapped[int] = mapped_column(Integer, default=7, comment="提前几天提醒")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AnniversaryPlan(Base):
    """纪念日安排项"""
    __tablename__ = "anniversary_plan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    anniversary_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    plan_type: Mapped[str] = mapped_column(
        SAEnum("gift", "restaurant", "cake", "activity", "other", name="plan_type"),
        nullable=False,
        comment="礼物/餐厅/蛋糕/活动/其他",
    )
    content: Mapped[str] = mapped_column(String(200), nullable=False, comment="安排内容")
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "arranged", name="plan_status"),
        default="pending",
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True, comment="预算金额")
    income_expense_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="关联F3")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class WishListItem(Base):
    """喜好愿望"""
    __tablename__ = "wish_list"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    member_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, comment="所属成员")
    content: Mapped[str] = mapped_column(String(200), nullable=False, comment="愿望内容")
    category: Mapped[str] = mapped_column(String(50), default="", comment="分类")
    source: Mapped[str] = mapped_column(
        SAEnum("manual", "inferred", name="wish_source"),
        default="manual",
        comment="手动录入/系统推断",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )