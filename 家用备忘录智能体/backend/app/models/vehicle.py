# -*- coding: utf-8 -*-
"""
F4 车辆管理模型。
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import String, Text, Integer, Enum as SAEnum, DateTime, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class VehicleInfo(Base):
    """车辆信息"""
    __tablename__ = "vehicle_info"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    brand: Mapped[str] = mapped_column(String(50), default="", comment="品牌")
    model: Mapped[str] = mapped_column(String(50), default="", comment="型号")
    plate_number: Mapped[str] = mapped_column(String(20), default="", comment="车牌号")
    purchase_date: Mapped[date] = mapped_column(Date, nullable=True, comment="购买日期")
    insurance_expire: Mapped[date] = mapped_column(Date, nullable=True, comment="保险到期日")
    insurance_company: Mapped[str] = mapped_column(String(100), default="", comment="保险公司")
    maintenance_shop: Mapped[str] = mapped_column(String(100), default="", comment="4S店名称")
    maintenance_address: Mapped[str] = mapped_column(String(200), default="", comment="4S店地址")
    maintenance_contact: Mapped[str] = mapped_column(String(50), default="", comment="联系人")
    maintenance_phone: Mapped[str] = mapped_column(String(20), default="", comment="联系电话")
    next_maintenance_date: Mapped[date] = mapped_column(Date, nullable=True, comment="下次保养日期")
    next_maintenance_mileage: Mapped[int] = mapped_column(Integer, nullable=True, comment="下次保养里程")
    next_inspection_date: Mapped[date] = mapped_column(Date, nullable=True, comment="下次年检日期")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class VehicleExpense(Base):
    """用车支出"""
    __tablename__ = "vehicle_expense"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    vehicle_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    expense_type: Mapped[str] = mapped_column(
        SAEnum(
            "fuel", "charging", "insurance", "violation", "maintenance", "other",
            name="vehicle_expense_type",
        ),
        nullable=False,
        comment="加油/充电/保险/违章/保养/其他",
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    location: Mapped[str] = mapped_column(String(100), default="", comment="地点")
    date: Mapped[date] = mapped_column(Date, nullable=False, comment="日期")
    note: Mapped[str] = mapped_column(Text, default="", comment="备注")
    income_expense_id: Mapped[str] = mapped_column(String(36), nullable=True, comment="关联F3")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class DrivingLicense(Base):
    """驾驶分记录"""
    __tablename__ = "driving_license"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    member_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, comment="家庭成员")
    violation_date: Mapped[date] = mapped_column(Date, nullable=False, comment="违章日期")
    location: Mapped[str] = mapped_column(String(100), default="", comment="违章地点")
    reason: Mapped[str] = mapped_column(String(200), default="", comment="违章原因")
    deduction: Mapped[int] = mapped_column(Integer, default=0, comment="扣分")
    fine: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True, comment="罚款金额")
    remaining_points: Mapped[int] = mapped_column(Integer, default=12, comment="剩余分数")
    clear_date: Mapped[date] = mapped_column(Date, nullable=True, comment="清零日期")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )