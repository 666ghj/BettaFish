# -*- coding: utf-8 -*-
"""
F1 周期性缴费模型。
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import String, Integer, Enum as SAEnum, DateTime, Date, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class PaymentItem(Base):
    """缴费项目配置"""
    __tablename__ = "payment_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(
        SAEnum("water", "electric", "gas", "property", name="payment_name"),
        nullable=False,
        comment="水费/电费/燃气费/物业费",
    )
    frequency: Mapped[str] = mapped_column(
        SAEnum("monthly", "half_yearly", name="payment_frequency"),
        nullable=False,
    )
    reminder_day: Mapped[int] = mapped_column(Integer, default=15, comment="每月提醒日")
    advance_days: Mapped[int] = mapped_column(Integer, default=3, comment="提前几天提醒")
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class PaymentRecord(Base):
    """缴费记录"""
    __tablename__ = "payment_record"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    payment_item_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    paid_date: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("unpaid", "paid", "overdue", name="payment_status"),
        default="unpaid",
    )
    income_expense_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="关联F3收支记录")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )