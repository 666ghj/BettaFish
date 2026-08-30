# -*- coding: utf-8 -*-
"""
F4 车辆管理接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.family import FamilyMember
from app.models.vehicle import VehicleInfo, VehicleExpense, DrivingLicense
from app.core.deps import get_current_member
from app.schemas.vehicle import (
    VehicleInfoUpdate, VehicleInfoOut,
    VehicleExpenseCreate, VehicleExpenseOut,
    DrivingLicenseCreate, DrivingLicenseOut,
)

router = APIRouter()


@router.get("/info", response_model=VehicleInfoOut)
async def get_vehicle_info(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    result = await db.execute(
        select(VehicleInfo).where(VehicleInfo.family_id == member.family_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        # 返回空车辆信息，让前端引导用户填写
        return VehicleInfoOut(
            id="", brand="", model="", plate_number="",
            maintenance_shop="", maintenance_address="",
            maintenance_contact="", maintenance_phone="",
            insurance_company="",
        )
    return vehicle


@router.put("/info", response_model=VehicleInfoOut)
async def update_vehicle_info(
    req: VehicleInfoUpdate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    result = await db.execute(
        select(VehicleInfo).where(VehicleInfo.family_id == member.family_id)
    )
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        vehicle = VehicleInfo(family_id=member.family_id)
        db.add(vehicle)

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vehicle, key, value)

    return vehicle


@router.get("/expenses", response_model=list[VehicleExpenseOut])
async def list_vehicle_expenses(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    result = await db.execute(
        select(VehicleExpense)
        .join(VehicleInfo, VehicleExpense.vehicle_id == VehicleInfo.id)
        .where(VehicleInfo.family_id == member.family_id)
        .order_by(VehicleExpense.date.desc())
    )
    return result.scalars().all()


@router.post("/expenses", response_model=VehicleExpenseOut)
async def create_vehicle_expense(
    req: VehicleExpenseCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    # 获取车辆ID
    result = await db.execute(
        select(VehicleInfo).where(VehicleInfo.family_id == member.family_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先填写车辆信息")

    expense = VehicleExpense(vehicle_id=vehicle.id, **req.model_dump())
    db.add(expense)
    await db.flush()

    # 自动创建 F3 收支记录
    from app.models.finance import IncomeExpense
    expense_type_map = {
        "fuel": "加油", "charging": "充电", "insurance": "车险",
        "violation": "违章", "maintenance": "保养", "other": "用车",
    }
    expense_name = expense_type_map.get(req.expense_type, "用车")

    ie = IncomeExpense(
        family_id=member.family_id,
        type="expense",
        amount=req.amount,
        category="vehicle",
        note=f"{expense_name}: {req.location or ''} {req.note or ''}",
        payer_id=member.id,
        record_date=req.date,
        source_type="vehicle",
        source_id=expense.id,
    )
    db.add(ie)
    await db.flush()
    expense.income_expense_id = ie.id

    return expense


@router.get("/license", response_model=list[DrivingLicenseOut])
async def list_driving_license(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    result = await db.execute(
        select(DrivingLicense).where(DrivingLicense.member_id == member.id)
        .order_by(DrivingLicense.violation_date.desc())
    )
    return result.scalars().all()


@router.post("/license", response_model=DrivingLicenseOut)
async def add_violation(
    req: DrivingLicenseCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    # 计算剩余分数
    result = await db.execute(
        select(func.sum(DrivingLicense.deduction))
        .where(DrivingLicense.member_id == member.id)
    )
    total_deducted = result.scalar() or 0
    remaining = max(0, 12 - total_deducted - req.deduction)

    violation = DrivingLicense(
        member_id=member.id,
        remaining_points=remaining,
        **req.model_dump(),
    )
    db.add(violation)
    return violation