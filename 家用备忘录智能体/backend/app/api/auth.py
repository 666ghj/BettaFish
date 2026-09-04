# -*- coding: utf-8 -*-
"""
微信登录接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from loguru import logger

from app.database import get_db
from app.config import settings
from app.models.family import FamilyMember
from app.core.security import create_access_token
from app.core.deps import get_current_member
from app.schemas.auth import LoginRequest, LoginResponse, MemberInfo

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """微信登录：code -> openid -> 创建/查询用户 -> 返回 JWT"""
    # 调用微信 code2session 接口
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            settings.WECHAT_LOGIN_URL,
            params={
                "appid": settings.WECHAT_APPID,
                "secret": settings.WECHAT_SECRET,
                "js_code": req.code,
                "grant_type": "authorization_code",
            },
        )
        data = resp.json()

    if "openid" not in data:
        logger.error(f"微信登录失败: {data}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="微信登录失败")

    openid = data["openid"]

    # 查询或创建用户
    result = await db.execute(select(FamilyMember).where(FamilyMember.openid == openid))
    member = result.scalar_one_or_none()

    if member is None:
        member = FamilyMember(openid=openid)
        db.add(member)
        await db.flush()

    # 生成 JWT
    token = create_access_token({"sub": member.id, "openid": openid})

    return LoginResponse(
        token=token,
        member_id=member.id,
        has_family=bool(member.family_id),
        role=member.role,
    )


@router.get("/me", response_model=MemberInfo)
async def get_me(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户信息"""
    return member