# -*- coding: utf-8 -*-
"""
F3 家庭收支记录接口。
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract

from app.database import get_db
from app.models.family import FamilyMember
from app.models.finance import IncomeExpense
from app.core.deps import get_current_member
from app.schemas.finance import (
    FinanceRecordCreate, FinanceRecordUpdate,
    FinanceRecordOut, MonthlyStats,
)

router = APIRouter()


@router.get("/records", response_model=list[FinanceRecordOut])
async def list_finance_records(
    year: int | None = None,
    month: int | None = None,
    category: str | None = None,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    query = select(IncomeExpense).where(IncomeExpense.family_id == member.family_id)

    if year and month:
        query = query.where(
            extract("year", IncomeExpense.record_date) == year,
            extract("month", IncomeExpense.record_date) == month,
        )
    if category:
        query = query.where(IncomeExpense.category == category)

    query = query.order_by(IncomeExpense.record_date.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats", response_model=MonthlyStats)
async def get_monthly_stats(
    year: int | None = None,
    month: int | None = None,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """获取月度统计"""
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    today = date.today()
    y = year or today.year
    m = month or today.month

    records = await db.execute(
        select(IncomeExpense).where(
            IncomeExpense.family_id == member.family_id,
            extract("year", IncomeExpense.record_date) == y,
            extract("month", IncomeExpense.record_date) == m,
        )
    )
    records = records.scalars().all()

    total_expense = sum(float(r.amount) for r in records if r.type == "expense")
    total_income = sum(float(r.amount) for r in records if r.type == "income")

    by_category = {}
    for r in records:
        if r.type == "expense":
            cat = r.category or "未分类"
            by_category[cat] = by_category.get(cat, 0) + float(r.amount)

    return MonthlyStats(
        month=f"{y}-{m:02d}",
        total_expense=total_expense,
        total_income=total_income,
        by_category=by_category,
    )


@router.post("/records", response_model=FinanceRecordOut)
async def create_finance_record(
    req: FinanceRecordCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    record = IncomeExpense(
        family_id=member.family_id,
        **req.model_dump(),
    )
    db.add(record)
    return record


@router.put("/records/{record_id}", response_model=FinanceRecordOut)
async def update_finance_record(
    record_id: str,
    req: FinanceRecordUpdate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IncomeExpense).where(
            IncomeExpense.id == record_id,
            IncomeExpense.family_id == member.family_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)

    return record