# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional
from datetime import date
from decimal import Decimal


class VehicleInfoUpdate(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    plate_number: Optional[str] = None
    purchase_date: Optional[date] = None
    insurance_expire: Optional[date] = None
    insurance_company: Optional[str] = None
    maintenance_shop: Optional[str] = None
    maintenance_address: Optional[str] = None
    maintenance_contact: Optional[str] = None
    maintenance_phone: Optional[str] = None
    next_maintenance_date: Optional[date] = None
    next_maintenance_mileage: Optional[int] = None
    next_inspection_date: Optional[date] = None


class VehicleInfoOut(BaseModel):
    id: str
    brand: str
    model: str
    plate_number: str
    purchase_date: Optional[date] = None
    insurance_expire: Optional[date] = None
    insurance_company: str
    maintenance_shop: str
    maintenance_address: str
    maintenance_contact: str
    maintenance_phone: str
    next_maintenance_date: Optional[date] = None
    next_maintenance_mileage: Optional[int] = None
    next_inspection_date: Optional[date] = None

    class Config:
        from_attributes = True


class VehicleExpenseCreate(BaseModel):
    expense_type: str
    amount: Decimal
    location: str = ""
    date: date
    note: str = ""


class VehicleExpenseOut(BaseModel):
    id: str
    expense_type: str
    amount: Decimal
    location: str
    date: date
    note: str

    class Config:
        from_attributes = True


class DrivingLicenseCreate(BaseModel):
    violation_date: date
    location: str = ""
    reason: str = ""
    deduction: int = 0
    fine: Optional[Decimal] = None


class DrivingLicenseOut(BaseModel):
    id: str
    violation_date: date
    location: str
    reason: str
    deduction: int
    fine: Optional[Decimal] = None
    remaining_points: int

    class Config:
        from_attributes = True