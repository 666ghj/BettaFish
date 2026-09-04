# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from decimal import Decimal


class ShoppingItemCreate(BaseModel):
    list_type: str  # household / husband / wife
    name: str
    category: str = ""
    estimated_price: Optional[Decimal] = None
    purchase_reason: str = ""
    image: str = ""


class ShoppingItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    estimated_price: Optional[Decimal] = None
    purchase_reason: Optional[str] = None
    image: Optional[str] = None


class ShoppingItemOut(BaseModel):
    id: str
    list_type: str
    name: str
    category: str
    image: str
    estimated_price: Optional[Decimal] = None
    purchase_reason: str
    status: str
    actual_price: Optional[Decimal] = None
    purchase_method: str
    purchase_date: Optional[date] = None
    created_by: str
    assignee: Optional[str] = None
    agreements: List[dict] = []
    comments: List[dict] = []

    class Config:
        from_attributes = True


class AgreementRequest(BaseModel):
    agreement: bool


class PurchaseRequest(BaseModel):
    actual_price: Decimal
    purchase_method: str = ""
    purchase_date: date


class CommentCreate(BaseModel):
    content: str
    to_member_id: Optional[str] = None
    parent_id: Optional[str] = None