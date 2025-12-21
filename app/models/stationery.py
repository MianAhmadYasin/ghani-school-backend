"""
Stationery Models for School Management System
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

class StationeryItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    unit_price: Decimal = Field(..., ge=0)
    stock_quantity: int = Field(default=0, ge=0)
    minimum_stock: int = Field(default=10, ge=0)
    supplier: Optional[str] = None

class StationeryItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    unit_price: Optional[Decimal] = Field(None, ge=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    minimum_stock: Optional[int] = Field(None, ge=0)
    supplier: Optional[str] = None

class StationeryItemResponse(BaseModel):
    id: str
    name: str
    category: str
    description: Optional[str]
    unit_price: Decimal
    stock_quantity: int
    minimum_stock: int
    supplier: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StationeryDistributionCreate(BaseModel):
    student_id: str
    item_id: str
    quantity: int = Field(..., gt=0)
    distributed_date: date = Field(default_factory=date.today)
    notes: Optional[str] = None

class StationeryDistributionUpdate(BaseModel):
    quantity: Optional[int] = Field(None, gt=0)
    distributed_date: Optional[date] = None
    notes: Optional[str] = None

class StationeryDistributionResponse(BaseModel):
    id: str
    student_id: str
    item_id: str
    quantity: int
    distributed_date: date
    distributed_by: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True















