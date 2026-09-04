# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional, List


class FamilyCreateRequest(BaseModel):
    name: str = "我的家庭"
    role: str = "husband"  # 创建者角色


class FamilyJoinRequest(BaseModel):
    invite_code: str
    role: str = "wife"  # 加入者角色


class FamilyInfo(BaseModel):
    id: str
    name: str
    invite_code: Optional[str] = None
    members: List[dict] = []

    class Config:
        from_attributes = True


class RefreshCodeResponse(BaseModel):
    invite_code: str
    expire_at: str