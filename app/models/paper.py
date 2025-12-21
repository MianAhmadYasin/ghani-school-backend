"""
Paper/Exam Paper Models for School Management System
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime
from enum import Enum

class TermType(str, Enum):
    FIRST_TERM = "first_term"
    SECOND_TERM = "second_term"
    THIRD_TERM = "third_term"

class FileType(str, Enum):
    PDF = "pdf"
    WORD = "word"
    IMAGE = "image"
    DOCX = "docx"

class PaperCreate(BaseModel):
    class_id: str = Field(..., description="ID of the class")
    class_name: str = Field(..., description="Name of the class")
    subject: str = Field(..., min_length=1, max_length=100)
    term: TermType
    year: int = Field(..., ge=2020, le=2100)
    file_url: str = Field(..., description="URL or path to the uploaded file")
    file_name: str = Field(..., description="Original file name")
    file_type: str = Field(..., description="File extension/type")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    description: Optional[str] = Field(None, max_length=500)

class PaperUpdate(BaseModel):
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    subject: Optional[str] = Field(None, min_length=1, max_length=100)
    term: Optional[TermType] = None
    year: Optional[int] = Field(None, ge=2020, le=2100)
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)

class PaperResponse(BaseModel):
    id: str
    class_id: str
    class_name: str
    subject: str
    term: str
    year: int
    file_url: str
    file_name: str
    file_type: str
    file_size: Optional[int]
    description: Optional[str]
    uploaded_by: str
    uploaded_by_name: Optional[str]
    upload_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaperStats(BaseModel):
    total_papers: int
    papers_by_term: dict
    papers_by_class: dict
    papers_by_subject: dict
    papers_by_year: dict
    recent_uploads: int

