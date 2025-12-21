"""
Exam Management Models for School Management System
Supports approval workflow, bulk uploads, and flexible exam types
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


class ExamType(str, Enum):
    TERM_EXAM = "term_exam"
    MID_TERM = "mid_term"
    FINAL = "final"
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"
    ANNUAL = "annual"
    CUSTOM = "custom"


class ExamStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResultStatus(str, Enum):
    ACTIVE = "active"
    ABSENT = "absent"
    ABSENT_WITH_EXCUSE = "absent_with_excuse"
    INCOMPLETE = "incomplete"


# Exam Models
class ExamBase(BaseModel):
    exam_name: str = Field(..., min_length=1, max_length=200, description="Name of the exam")
    exam_type: ExamType
    term: str = Field(..., description="Term (First Term, Second Term, Third Term, Final)")
    academic_year: str = Field(..., description="Academic year (e.g., 2024-2025)")
    class_id: str = Field(..., description="ID of the class")
    subject: str = Field(..., min_length=1, max_length=100)
    total_marks: float = Field(100.00, ge=1, le=10000, description="Total marks for the exam")
    passing_marks: float = Field(50.00, ge=0, description="Passing marks threshold")
    exam_date: Optional[date] = None
    duration_minutes: Optional[int] = Field(None, ge=1, description="Exam duration in minutes")
    instructions: Optional[str] = Field(None, max_length=1000)

    @field_validator('passing_marks')
    @classmethod
    def validate_passing_marks(cls, v: float, info) -> float:
        total = info.data.get('total_marks', 100.0)
        if v > total:
            raise ValueError(f"Passing marks ({v}) cannot exceed total marks ({total})")
        return v


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    exam_name: Optional[str] = Field(None, min_length=1, max_length=200)
    exam_type: Optional[ExamType] = None
    term: Optional[str] = None
    academic_year: Optional[str] = None
    class_id: Optional[str] = None
    subject: Optional[str] = Field(None, min_length=1, max_length=100)
    total_marks: Optional[float] = Field(None, ge=1, le=10000)
    passing_marks: Optional[float] = Field(None, ge=0)
    exam_date: Optional[date] = None
    duration_minutes: Optional[int] = Field(None, ge=1)
    instructions: Optional[str] = Field(None, max_length=1000)
    status: Optional[ExamStatus] = None


class ExamResponse(ExamBase):
    id: str
    created_by: str
    status: ExamStatus
    created_at: datetime
    updated_at: Optional[datetime]
    created_by_name: Optional[str] = None

    class Config:
        from_attributes = True


# Exam Paper Models (enhanced)
class PaperApprovalRequest(BaseModel):
    rejection_reason: Optional[str] = Field(None, max_length=500)
    comments: Optional[str] = Field(None, max_length=1000)


class PaperWithApproval(BaseModel):
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
    approval_status: ApprovalStatus
    exam_id: Optional[str]
    submitted_for_approval_at: Optional[datetime]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    rejected_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


# Exam Result Models
class ExamResultBase(BaseModel):
    exam_id: str
    student_id: str
    marks_obtained: float = Field(..., ge=0, description="Marks obtained by student")
    total_marks: float = Field(..., ge=1, description="Total marks for the exam")
    grade: Optional[str] = None
    status: ResultStatus = ResultStatus.ACTIVE
    remarks: Optional[str] = Field(None, max_length=500)

    @field_validator('marks_obtained')
    @classmethod
    def validate_marks(cls, v: float, info) -> float:
        total = info.data.get('total_marks', 100.0)
        if v > total:
            raise ValueError(f"Marks obtained ({v}) cannot exceed total marks ({total})")
        return v


class ExamResultCreate(ExamResultBase):
    pass


class ExamResultUpdate(BaseModel):
    marks_obtained: Optional[float] = Field(None, ge=0)
    total_marks: Optional[float] = Field(None, ge=1)
    grade: Optional[str] = None
    status: Optional[ResultStatus] = None
    remarks: Optional[str] = Field(None, max_length=500)


class ExamResultResponse(ExamResultBase):
    id: str
    percentage: float
    uploaded_by: str
    uploaded_by_name: Optional[str] = None
    uploaded_at: datetime
    created_at: datetime
    updated_at: Optional[datetime]
    student_name: Optional[str] = None
    admission_number: Optional[str] = None

    class Config:
        from_attributes = True


# Bulk Upload Models
class BulkResultEntry(BaseModel):
    student_id: Optional[str] = None
    admission_number: Optional[str] = None
    student_name: Optional[str] = None
    marks_obtained: float
    status: Optional[ResultStatus] = ResultStatus.ACTIVE
    remarks: Optional[str] = None


class BulkResultUpload(BaseModel):
    exam_id: str
    results: List[BulkResultEntry]
    overwrite_existing: bool = False


class BulkUploadValidation(BaseModel):
    valid: bool
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    valid_entries: int = 0
    invalid_entries: int = 0


class BulkUploadResponse(BaseModel):
    success_count: int
    error_count: int
    errors: List[Dict[str, Any]] = []
    message: str


# Exam Settings Models
class ExamSettingsBase(BaseModel):
    school_name: str = Field(..., min_length=1, max_length=200)
    terms_config: List[str] = Field(default_factory=lambda: ["First Term", "Second Term", "Third Term", "Final"])
    exam_types: List[str] = Field(default_factory=lambda: ["term_exam", "mid_term", "final", "quiz", "assignment", "annual"])
    default_grading_criteria: Optional[Dict[str, Any]] = None
    bulk_upload_enabled: bool = True
    approval_required: bool = True
    auto_calculate_grade: bool = True


class ExamSettingsUpdate(BaseModel):
    school_name: Optional[str] = Field(None, min_length=1, max_length=200)
    terms_config: Optional[List[str]] = None
    exam_types: Optional[List[str]] = None
    default_grading_criteria: Optional[Dict[str, Any]] = None
    bulk_upload_enabled: Optional[bool] = None
    approval_required: Optional[bool] = None
    auto_calculate_grade: Optional[bool] = None


class ExamSettingsResponse(ExamSettingsBase):
    id: str
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True







