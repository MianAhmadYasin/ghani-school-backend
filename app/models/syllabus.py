from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SyllabusBase(BaseModel):
    class_id: str
    class_name: str
    subject: str
    term: str  # first_term, second_term, third_term, annual
    year: int
    file_url: str
    file_name: str
    file_type: str
    file_size: Optional[int] = None


class SyllabusCreate(SyllabusBase):
    """Schema for creating a new syllabus"""
    pass


class SyllabusUpdate(BaseModel):
    """Schema for updating syllabus - all fields optional"""
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    subject: Optional[str] = None
    term: Optional[str] = None
    year: Optional[int] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None


class SyllabusResponse(SyllabusBase):
    """Schema for syllabus response"""
    id: str
    uploaded_by: str
    upload_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyllabusStats(BaseModel):
    """Statistics for syllabuses"""
    total_syllabuses: int
    syllabuses_by_term: dict
    syllabuses_by_class: dict
    syllabuses_by_subject: dict
    recent_uploads: int













