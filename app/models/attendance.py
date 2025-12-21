from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Optional
from datetime import date, datetime, timedelta
from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class AttendanceBase(BaseModel):
    user_id: str
    date: date
    status: AttendanceStatus
    marked_by: str
    remarks: Optional[str] = None
    
    @field_validator('date')
    @classmethod
    def validate_date(cls, v: date) -> date:
        """Validate attendance date is not in the future and not too old."""
        today = date.today()
        
        # Don't allow future dates
        if v > today:
            raise ValueError(f"Attendance date cannot be in the future. Date: {v}, Today: {today}")
        
        # Don't allow dates older than 1 year (reasonable limit)
        one_year_ago = today - timedelta(days=365)
        if v < one_year_ago:
            raise ValueError(f"Attendance date cannot be older than 1 year. Date: {v}")
        
        return v


class AttendanceCreate(BaseModel):
    user_id: str
    date: date
    status: AttendanceStatus
    remarks: Optional[str] = None
    
    @field_validator('date')
    @classmethod
    def validate_date(cls, v: date) -> date:
        """Validate attendance date is not in the future and not too old."""
        today = date.today()
        
        # Don't allow future dates
        if v > today:
            raise ValueError(f"Attendance date cannot be in the future. Date: {v}, Today: {today}")
        
        # Don't allow dates older than 1 year
        one_year_ago = today - timedelta(days=365)
        if v < one_year_ago:
            raise ValueError(f"Attendance date cannot be older than 1 year. Date: {v}")
        
        return v
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user_id is not empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("User ID cannot be empty")
        return v.strip()


class AttendanceUpdate(BaseModel):
    status: Optional[AttendanceStatus] = None
    remarks: Optional[str] = None


class AttendanceResponse(AttendanceBase):
    id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BulkAttendanceCreate(BaseModel):
    attendances: list[AttendanceCreate]












