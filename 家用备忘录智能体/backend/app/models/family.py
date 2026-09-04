# -*- coding: utf-8 -*-
"""
家庭空间与家庭成员模型。
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Enum as SAEnum, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Family(Base):
    __tablename__ = "family"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(50), default="我的家庭")
    invite_code: Mapped[str] = mapped_column(String(10), nullable=True, index=True)
    invite_code_expire: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    members = relationship("FamilyMember", back_populates="family")


class FamilyMember(Base):
    __tablename__ = "family_member"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    family_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role: Mapped[str] = mapped_column(
        SAEnum("husband", "wife", name="member_role"), nullable=True
    )
    nickname: Mapped[str] = mapped_column(String(50), default="")
    avatar: Mapped[str] = mapped_column(String(256), default="")
    notify_channels: Mapped[str] = mapped_column(
        String(100), default='["wechat"]',
        comment="通知渠道 JSON 数组，如 ['wechat','sms']",
    )
    quiet_hours: Mapped[str] = mapped_column(
        String(50), nullable=True,
        comment="免打扰时段 JSON，如 {\"start\":\"22:00\",\"end\":\"08:00\"}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    family = relationship("Family", back_populates="members")