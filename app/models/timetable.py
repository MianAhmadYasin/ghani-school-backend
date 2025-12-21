from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, time


class TimetableBase(BaseModel):
    class_id: str
    period_duration_minutes: int = Field(ge=20, le=120)
    break_duration_minutes: int = Field(ge=0, le=60)
    total_periods_per_day: int = Field(ge=1, le=12)
    working_days: List[int]  # [1, 2, 3, 4, 5] for Monday-Friday (1=Monday, 7=Sunday)
    start_time: str  # "08:00:00"
    status: str = "draft"  # draft or final


class TimetableCreate(TimetableBase):
    """Schema for creating a new timetable"""
    pass


class TimetableUpdate(BaseModel):
    """Schema for updating timetable - all fields optional"""
    class_id: Optional[str] = None
    period_duration_minutes: Optional[int] = None
    break_duration_minutes: Optional[int] = None
    total_periods_per_day: Optional[int] = None
    working_days: Optional[List[int]] = None
    start_time: Optional[str] = None
    status: Optional[str] = None


class TimetableResponse(TimetableBase):
    """Schema for timetable response"""
    id: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimetableEntryBase(BaseModel):
    timetable_id: str
    day_of_week: int = Field(ge=1, le=7)  # 1=Monday, 7=Sunday
    period_number: int
    is_break: bool = False
    subject: Optional[str] = None
    teacher_id: Optional[str] = None
    class_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class TimetableEntryCreate(TimetableEntryBase):
    """Schema for creating a timetable entry"""
    pass


class TimetableEntryUpdate(BaseModel):
    """Schema for updating timetable entry"""
    day_of_week: Optional[int] = None
    period_number: Optional[int] = None
    is_break: Optional[bool] = None
    subject: Optional[str] = None
    teacher_id: Optional[str] = None
    class_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class TimetableEntryResponse(TimetableEntryBase):
    """Schema for timetable entry response"""
    id: str

    class Config:
        from_attributes = True


class TimetableWithEntries(TimetableResponse):
    """Timetable with its entries"""
    entries: List[TimetableEntryResponse] = []


class AutoGenerateRequest(BaseModel):
    """Request to auto-generate timetable"""
    class_id: str
    period_duration_minutes: int = Field(ge=20, le=120)
    break_duration_minutes: int = Field(ge=0, le=60)
    total_periods_per_day: int = Field(ge=1, le=12)
    working_days: List[int]  # [1, 2, 3, 4, 5] for Monday-Friday
    start_time: str
    subjects: List[str]  # List of subjects to schedule
    teacher_assignments: dict  # {subject: teacher_id}
    break_after_period: int = 2  # Insert break after this period number





