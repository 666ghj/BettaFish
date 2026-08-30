# -*- coding: utf-8 -*-
"""
FastAPI 依赖注入。
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import verify_token
from app.models.family import FamilyMember

security = HTTPBearer()


async def get_current_member(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> FamilyMember:
    """获取当前登录的家庭成员"""
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的token")

    member_id = payload.get("sub")
    if not member_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的token")

    result = await db.execute(select(FamilyMember).where(FamilyMember.id == member_id))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="成员不存在")

    return member