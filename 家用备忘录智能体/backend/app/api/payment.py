# -*- coding: utf-8 -*-
"""
F1 周期性缴费接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.family import FamilyMember
from app.models.payment import PaymentItem, PaymentRecord
from app.core.deps import get_current_member
from app.schemas.payment import (
    PaymentItemOut, PaymentItemUpdate,
    PaymentRecordOut, PaymentRecordCreate,
)

router = APIRouter()


@router.get("/items", response_model=list[PaymentItemOut])
async def list_payment_items(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")
    result = await db.execute(
        select(PaymentItem).where(PaymentItem.family_id == member.family_id)
    )
    return result.scalars().all()


@router.put("/items/{item_id}", response_model=PaymentItemOut)
async def update_payment_item(
    item_id: str,
    req: PaymentItemUpdate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PaymentItem).where(PaymentItem.id == item_id, PaymentItem.family_id == member.family_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="缴费项目不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    return item


@router.get("/records", response_model=list[PaymentRecordOut])
async def list_payment_records(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")
    # 联表查询
    result = await db.execute(
        select(PaymentRecord)
        .join(PaymentItem, PaymentRecord.payment_item_id == PaymentItem.id)
        .where(PaymentItem.family_id == member.family_id)
        .order_by(PaymentRecord.paid_date.desc())
    )
    return result.scalars().all()


@router.post("/records", response_model=PaymentRecordOut)
async def create_payment_record(
    req: PaymentRecordCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    record = PaymentRecord(**req.model_dump(), status="paid")
    db.add(record)
    await db.flush()

    # 自动创建 F3 收支记录
    from app.models.finance import IncomeExpense
    from app.models.payment import PaymentItem
    result = await db.execute(select(PaymentItem).where(PaymentItem.id == req.payment_item_id))
    payment_item = result.scalar_one_or_none()
    payment_name_map = {"water": "水费", "electric": "电费", "gas": "燃气费", "property": "物业费"}
    name = payment_name_map.get(payment_item.name, payment_item.name) if payment_item else "缴费"

    ie = IncomeExpense(
        family_id=member.family_id,
        type="expense",
        amount=req.actual_amount,
        category="utility",
        note=f"{name}缴纳",
        payer_id=member.id,
        record_date=req.paid_date,
        source_type="payment",
        source_id=record.id,
    )
    db.add(ie)
    await db.flush()
    record.income_expense_id = ie.id

    return record