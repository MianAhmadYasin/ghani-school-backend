from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Optional
from datetime import datetime
from app.core.grading_utils import calculate_grade, validate_marks


class GradeBase(BaseModel):
    student_id: str
    class_id: str
    subject: str
    marks: float
    grade: str
    term: str
    academic_year: str
    remarks: Optional[str] = None
    
    @field_validator('marks')
    @classmethod
    def validate_marks(cls, v: float) -> float:
        """Validate marks are in valid range (0-100)."""
        validate_marks(v, max_marks=100.0)
        return round(v, 2)
    
    @field_validator('grade')
    @classmethod
    def validate_grade(cls, v: str) -> str:
        """Validate grade name (allows custom grade names from grading schemes)."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Grade cannot be empty")
        # Allow any grade name - custom schemes may use different names
        # We'll validate against active scheme in the endpoint if needed
        return v.strip()
    
    @field_validator('term')
    @classmethod
    def validate_term(cls, v: str) -> str:
        """Validate term is a valid value. Normalize 'Final' to 'Annual'."""
        # Normalize 'Final' to 'Annual' for consistency
        if v == 'Final':
            return 'Annual'
        valid_terms = ['First Term', 'Second Term', 'Third Term', 'Final', 'Annual']
        if v not in valid_terms:
            raise ValueError(f"Invalid term '{v}'. Must be one of: {', '.join(valid_terms)}")
        return v
    
    @field_validator('academic_year')
    @classmethod
    def validate_academic_year(cls, v: str) -> str:
        """Validate academic year format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Academic year cannot be empty")
        # Accept formats like "2024-2025" or "2024"
        if len(v) < 4:
            raise ValueError(f"Invalid academic year format: {v}")
        return v.strip()
    
    @field_validator('subject')
    @classmethod
    def validate_subject(cls, v: str) -> str:
        """Validate subject name."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Subject cannot be empty")
        return v.strip()
    
    @model_validator(mode='after')
    def validate_marks_grade_match(self):
        """Ensure marks and grade are consistent (optional check, can be overridden)."""
        # Note: This validation is optional since schools may have custom grading schemes
        # The actual grade calculation will use the active grading scheme in the endpoint
        # We skip strict validation here to allow flexibility
        return self


class GradeCreate(BaseModel):
    student_id: str
    class_id: str
    subject: str
    marks: float
    grade: Optional[str] = None  # Optional - will be auto-calculated if not provided
    term: str
    academic_year: str
    remarks: Optional[str] = None
    
    @field_validator('marks')
    @classmethod
    def validate_marks(cls, v: float) -> float:
        """Validate marks are in valid range (0-100)."""
        validate_marks(v, max_marks=100.0)
        return round(v, 2)
    
    @field_validator('grade')
    @classmethod
    def validate_grade(cls, v: Optional[str]) -> Optional[str]:
        """Validate grade if provided (allows custom grade names)."""
        if v is None:
            return None
        if len(v.strip()) == 0:
            raise ValueError("Grade cannot be empty")
        # Allow any grade name - custom schemes may use different names
        return v.strip()
    
    @field_validator('term')
    @classmethod
    def validate_term(cls, v: str) -> str:
        """Validate term is a valid value."""
        valid_terms = ['First Term', 'Second Term', 'Third Term', 'Annual']
        if v not in valid_terms:
            raise ValueError(f"Invalid term '{v}'. Must be one of: {', '.join(valid_terms)}")
        return v
    
    @field_validator('academic_year')
    @classmethod
    def validate_academic_year(cls, v: str) -> str:
        """Validate academic year format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Academic year cannot be empty")
        return v.strip()
    
    @model_validator(mode='after')
    def calculate_grade_if_missing(self):
        """Auto-calculate grade from marks if not provided."""
        if self.grade is None:
            self.grade = calculate_grade(self.marks)
        return self


class GradeUpdate(BaseModel):
    marks: Optional[float] = None
    grade: Optional[str] = None
    remarks: Optional[str] = None
    
    @field_validator('marks')
    @classmethod
    def validate_marks(cls, v: Optional[float]) -> Optional[float]:
        """Validate marks are in valid range (0-100) if provided."""
        if v is not None:
            validate_marks(v, max_marks=100.0)
            return round(v, 2)
        return v
    
    @field_validator('grade')
    @classmethod
    def validate_grade(cls, v: Optional[str]) -> Optional[str]:
        """Validate grade if provided (allows custom grade names)."""
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError("Grade cannot be empty")
            # Allow any grade name - custom schemes may use different names
            return v.strip()
        return v


class GradeResponse(GradeBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class BulkGradeCreate(BaseModel):
    grades: list[GradeCreate]












