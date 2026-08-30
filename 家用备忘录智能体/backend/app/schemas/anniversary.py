# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from decimal import Decimal


class AnniversaryCreate(BaseModel):
    name: str
    date: date
    reminder_days: int = 7


class AnniversaryUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    reminder_days: Optional[int] = None
    is_active: Optional[bool] = None


class AnniversaryOut(BaseModel):
    id: str
    name: str
    date: date
    reminder_days: int
    is_active: bool
    plans: List[dict] = []

    class Config:
        from_attributes = True


class AnniversaryPlanCreate(BaseModel):
    plan_type: str  # gift / restaurant / cake / activity / other
    content: str
    amount: Optional[Decimal] = None


class AnniversaryPlanOut(BaseModel):
    id: str
    plan_type: str
    content: str
    status: str
    amount: Optional[Decimal] = None

    class Config:
        from_attributes = True


class WishItemCreate(BaseModel):
    content: str
    category: str = ""


class WishItemOut(BaseModel):
    id: str
    content: str
    category: str
    source: str
    created_at: str

    class Config:
        from_attributes = True