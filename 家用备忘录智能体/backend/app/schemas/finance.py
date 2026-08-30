# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from decimal import Decimal


class FinanceRecordCreate(BaseModel):
    type: str  # expense / income
    amount: Decimal
    category: str = ""
    note: str = ""
    payer_id: Optional[str] = None
    record_date: date


class FinanceRecordUpdate(BaseModel):
    amount: Optional[Decimal] = None
    category: Optional[str] = None
    note: Optional[str] = None
    payer_id: Optional[str] = None


class FinanceRecordOut(BaseModel):
    id: str
    type: str
    amount: Decimal
    category: str
    note: str
    payer_id: Optional[str] = None
    record_date: date
    source_type: str

    class Config:
        from_attributes = True


class MonthlyStats(BaseModel):
    month: str
    total_expense: float
    total_income: float
    by_category: dict