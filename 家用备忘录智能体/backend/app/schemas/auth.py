# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    code: str  # 微信 wx.login 返回的 code


class LoginResponse(BaseModel):
    token: str
    member_id: str
    has_family: bool
    role: Optional[str] = None


class MemberInfo(BaseModel):
    id: str
    openid: str
    role: Optional[str] = None
    nickname: str
    avatar: str
    created_at: str

    class Config:
        from_attributes = True