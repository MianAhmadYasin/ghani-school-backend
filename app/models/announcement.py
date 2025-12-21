"""
Announcement Models for School Management System
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from enum import Enum

class TargetAudience(str, Enum):
    ALL = "all"
    STUDENTS = "students"
    TEACHERS = "teachers"
    PARENTS = "parents"
    STAFF = "staff"

class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    target_audience: TargetAudience = TargetAudience.ALL
    priority: Priority = Priority.NORMAL
    start_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None
    is_active: bool = True

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    target_audience: Optional[TargetAudience] = None
    priority: Optional[Priority] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None

class AnnouncementResponse(BaseModel):
    id: str
    title: str
    content: str
    target_audience: str
    priority: str
    start_date: date
    end_date: Optional[date]
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True















