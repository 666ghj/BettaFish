# -*- coding: utf-8 -*-
"""
F7 纪念日/重要日期接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.family import FamilyMember
from app.models.anniversary import Anniversary, AnniversaryPlan, WishListItem
from app.core.deps import get_current_member
from app.schemas.anniversary import (
    AnniversaryCreate, AnniversaryUpdate, AnniversaryOut,
    AnniversaryPlanCreate, AnniversaryPlanOut,
    WishItemCreate, WishItemOut,
)

router = APIRouter()


@router.get("/list", response_model=list[AnniversaryOut])
async def list_anniversaries(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    result = await db.execute(
        select(Anniversary).where(Anniversary.family_id == member.family_id)
        .order_by(Anniversary.date)
    )
    anniversaries = result.scalars().all()

    output = []
    for a in anniversaries:
        plans = await db.execute(
            select(AnniversaryPlan).where(AnniversaryPlan.anniversary_id == a.id)
        )
        output.append(AnniversaryOut(
            **a.__dict__,
            plans=[{"id": p.id, "plan_type": p.plan_type, "content": p.content, "status": p.status}
                   for p in plans.scalars().all()],
        ))
    return output


@router.post("", response_model=AnniversaryOut)
async def create_anniversary(
    req: AnniversaryCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    anniversary = Anniversary(family_id=member.family_id, **req.model_dump())
    db.add(anniversary)

    # TODO: 创建备忘提醒（通过 memo_item 走统一提醒调度）

    return AnniversaryOut(**anniversary.__dict__, plans=[])


@router.put("/{anniversary_id}", response_model=AnniversaryOut)
async def update_anniversary(
    anniversary_id: str,
    req: AnniversaryUpdate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Anniversary).where(
            Anniversary.id == anniversary_id,
            Anniversary.family_id == member.family_id,
        )
    )
    anniversary = result.scalar_one_or_none()
    if not anniversary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="纪念日不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(anniversary, key, value)

    return AnniversaryOut(**anniversary.__dict__, plans=[])


@router.delete("/{anniversary_id}")
async def delete_anniversary(
    anniversary_id: str,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Anniversary).where(
            Anniversary.id == anniversary_id,
            Anniversary.family_id == member.family_id,
        )
    )
    anniversary = result.scalar_one_or_none()
    if not anniversary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="纪念日不存在")

    anniversary.is_active = False
    return {"message": "已删除"}


@router.get("/{anniversary_id}/plans", response_model=list[AnniversaryPlanOut])
async def list_anniversary_plans(
    anniversary_id: str,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnniversaryPlan).where(AnniversaryPlan.anniversary_id == anniversary_id)
    )
    return result.scalars().all()


@router.post("/{anniversary_id}/plans", response_model=AnniversaryPlanOut)
async def create_anniversary_plan(
    anniversary_id: str,
    req: AnniversaryPlanCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    plan = AnniversaryPlan(anniversary_id=anniversary_id, **req.model_dump())
    db.add(plan)
    return plan


@router.get("/wish-list", response_model=list[WishItemOut])
async def list_wish_list(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WishListItem).where(WishListItem.member_id == member.id)
        .order_by(WishListItem.created_at.desc())
    )
    return result.scalars().all()


@router.post("/wish-list", response_model=WishItemOut)
async def add_wish_item(
    req: WishItemCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    item = WishListItem(member_id=member.id, **req.model_dump())
    db.add(item)
    return item