from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Optional, List
from datetime import datetime


class GradingCriterionBase(BaseModel):
    grade_name: str
    min_marks: float
    max_marks: float
    gpa_value: float = 0.0
    is_passing: bool = True
    display_order: int = 0
    
    @field_validator('grade_name')
    @classmethod
    def validate_grade_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Grade name cannot be empty")
        return v.strip()
    
    @field_validator('min_marks', 'max_marks')
    @classmethod
    def validate_marks_range(cls, v: float) -> float:
        if not (0 <= v <= 100):
            raise ValueError("Marks must be between 0 and 100")
        return round(v, 2)
    
    @field_validator('gpa_value')
    @classmethod
    def validate_gpa(cls, v: float) -> float:
        if not (0 <= v <= 4.0):
            raise ValueError("GPA value must be between 0 and 4.0")
        return round(v, 2)
    
    @model_validator(mode='after')
    def validate_min_max(self):
        if self.min_marks > self.max_marks:
            raise ValueError("min_marks cannot be greater than max_marks")
        return self


class GradingCriterionCreate(GradingCriterionBase):
    pass


class GradingCriterionUpdate(BaseModel):
    grade_name: Optional[str] = None
    min_marks: Optional[float] = None
    max_marks: Optional[float] = None
    gpa_value: Optional[float] = None
    is_passing: Optional[bool] = None
    display_order: Optional[int] = None
    
    @field_validator('min_marks', 'max_marks')
    @classmethod
    def validate_marks_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0 <= v <= 100):
            raise ValueError("Marks must be between 0 and 100")
        return round(v, 2) if v is not None else None
    
    @field_validator('gpa_value')
    @classmethod
    def validate_gpa(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0 <= v <= 4.0):
            raise ValueError("GPA value must be between 0 and 4.0")
        return round(v, 2) if v is not None else None


class GradingCriterionResponse(GradingCriterionBase):
    id: str
    grading_scheme_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class GradingSchemeBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Scheme name cannot be empty")
        return v.strip()


class GradingSchemeCreate(GradingSchemeBase):
    criteria: List[GradingCriterionCreate]
    
    @model_validator(mode='after')
    def validate_criteria(self):
        if not self.criteria or len(self.criteria) == 0:
            raise ValueError("At least one grading criterion is required")
        
        # Check for overlapping mark ranges
        sorted_criteria = sorted(self.criteria, key=lambda x: x.display_order)
        for i in range(len(sorted_criteria) - 1):
            current = sorted_criteria[i]
            next_crit = sorted_criteria[i + 1]
            if current.max_marks >= next_crit.min_marks:
                raise ValueError(f"Overlapping mark ranges: {current.grade_name} ({current.min_marks}-{current.max_marks}) and {next_crit.grade_name} ({next_crit.min_marks}-{next_crit.max_marks})")
        
        return self


class GradingSchemeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Scheme name cannot be empty")
        return v.strip() if v else None


class GradingSchemeResponse(GradingSchemeBase):
    id: str
    criteria: List[GradingCriterionResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class BulkGradingSchemeUpdate(BaseModel):
    scheme_id: str
    criteria: List[GradingCriterionCreate]








