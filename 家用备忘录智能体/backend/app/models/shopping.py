# -*- coding: utf-8 -*-
"""
F2 购物清单模型。
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import String, Text, Enum as SAEnum, DateTime, Date, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class ShoppingItem(Base):
    """购物清单物品"""
    __tablename__ = "shopping_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    list_type: Mapped[str] = mapped_column(
        SAEnum("household", "husband", "wife", name="shopping_list_type"),
        nullable=False,
        comment="家用/老公个人/老婆个人",
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="物品名称")
    category: Mapped[str] = mapped_column(String(50), default="", comment="分类")
    image: Mapped[str] = mapped_column(String(256), default="", comment="图片URL")
    estimated_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True, comment="预估价格")
    purchase_reason: Mapped[str] = mapped_column(Text, default="", comment="购买理由")
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "bought", "cancelled", name="shopping_status"),
        default="pending",
    )
    actual_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True, comment="实际价格")
    purchase_method: Mapped[str] = mapped_column(String(50), default="", comment="购买方式")
    purchase_date: Mapped[date] = mapped_column(Date, nullable=True, comment="购买日期")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, comment="创建人member_id")
    assignee: Mapped[str] = mapped_column(String(36), nullable=True, comment="负责人member_id")
    income_expense_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="关联F3收支记录")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class HouseholdAgreement(Base):
    """家用清单同意表"""
    __tablename__ = "household_agreement"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shopping_item_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="家庭成员")
    agreement: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="同意/不同意")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ShoppingComment(Base):
    """购物清单评论"""
    __tablename__ = "shopping_comment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shopping_item_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    from_member_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="评论人")
    to_member_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="回复对象")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论内容")
    parent_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="父评论ID")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )