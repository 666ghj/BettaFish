# -*- coding: utf-8 -*-
"""
F3 家庭收支记录模型。
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import String, Text, Enum as SAEnum, DateTime, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class IncomeExpense(Base):
    """收支记录"""
    __tablename__ = "income_expense"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    type: Mapped[str] = mapped_column(
        SAEnum("expense", "income", name="ie_type"),
        nullable=False,
        comment="支出/收入",
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="", comment="分类")
    note: Mapped[str] = mapped_column(Text, default="", comment="备注")
    payer_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="谁付的")
    record_date: Mapped[date] = mapped_column(Date, nullable=False, comment="日期")
    source_type: Mapped[str] = mapped_column(
        String(50), default="manual",
        comment="来源类型: manual/shopping/payment/vehicle",
    )
    source_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="来源关联ID")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )