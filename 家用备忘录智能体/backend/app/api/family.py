# -*- coding: utf-8 -*-
"""
家庭空间与邀请码管理接口。
"""
import random
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app.models.family import Family, FamilyMember
from app.core.deps import get_current_member
from app.schemas.family import FamilyCreateRequest, FamilyJoinRequest, FamilyInfo, RefreshCodeResponse

router = APIRouter()


def generate_invite_code(length: int = 6) -> str:
    """生成6位邀请码"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


@router.post("/create", response_model=FamilyInfo)
async def create_family(
    req: FamilyCreateRequest,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """创建家庭空间，生成邀请码"""
    if member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已加入家庭，不能重复创建")

    family = Family(
        name=req.name,
        invite_code=generate_invite_code(),
        invite_code_expire=datetime.now(timezone.utc) + timedelta(hours=48),
    )
    db.add(family)
    await db.flush()

    # 更新成员
    member.family_id = family.id
    member.role = req.role

    return FamilyInfo(
        id=family.id,
        name=family.name,
        invite_code=family.invite_code,
        members=[{"id": member.id, "role": member.role, "nickname": member.nickname}],
    )


@router.post("/join")
async def join_family(
    req: FamilyJoinRequest,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """通过邀请码加入家庭"""
    if member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已加入家庭")

    # 查找有效邀请码
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Family).where(
            Family.invite_code == req.invite_code,
            Family.invite_code_expire > now,
        )
    )
    family = result.scalar_one_or_none()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀请码无效或已过期")

    member.family_id = family.id
    member.role = req.role

    return {"message": "加入成功", "family_id": family.id, "family_name": family.name}


@router.get("/info", response_model=FamilyInfo)
async def get_family_info(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """获取家庭信息"""
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    result = await db.execute(select(Family).where(Family.id == member.family_id))
    family = result.scalar_one_or_none()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="家庭不存在")

    members_result = await db.execute(
        select(FamilyMember).where(FamilyMember.family_id == family.id)
    )
    members = members_result.scalars().all()

    return FamilyInfo(
        id=family.id,
        name=family.name,
        invite_code=family.invite_code,
        members=[
            {"id": m.id, "role": m.role, "nickname": m.nickname, "avatar": m.avatar}
            for m in members
        ],
    )


@router.post("/refresh-code", response_model=RefreshCodeResponse)
async def refresh_invite_code(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """重新生成邀请码"""
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    new_code = generate_invite_code()
    expire_at = datetime.now(timezone.utc) + timedelta(hours=48)

    await db.execute(
        update(Family)
        .where(Family.id == member.family_id)
        .values(invite_code=new_code, invite_code_expire=expire_at)
    )

    return RefreshCodeResponse(
        invite_code=new_code,
        expire_at=expire_at.isoformat(),
    )