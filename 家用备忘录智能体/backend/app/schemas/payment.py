# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional
from datetime import date
from decimal import Decimal


class PaymentItemOut(BaseModel):
    id: str
    name: str
    frequency: str
    reminder_day: int
    advance_days: int
    estimated_amount: Optional[Decimal] = None
    is_active: bool

    class Config:
        from_attributes = True


class PaymentItemUpdate(BaseModel):
    reminder_day: Optional[int] = None
    advance_days: Optional[int] = None
    estimated_amount: Optional[Decimal] = None
    is_active: Optional[bool] = None


class PaymentRecordOut(BaseModel):
    id: str
    payment_item_id: str
    actual_amount: Optional[Decimal] = None
    paid_date: Optional[date] = None
    status: str

    class Config:
        from_attributes = True


class PaymentRecordCreate(BaseModel):
    payment_item_id: str
    actual_amount: Decimal
    paid_date: date