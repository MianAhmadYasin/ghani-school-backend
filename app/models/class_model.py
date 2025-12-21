from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class ClassBase(BaseModel):
    name: str
    section: str
    teacher_id: Optional[str] = None
    academic_year: str


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    section: Optional[str] = None
    teacher_id: Optional[str] = None
    academic_year: Optional[str] = None


class ClassResponse(BaseModel):
    id: str
    name: str
    section: str
    teacher_id: Optional[str] = None
    academic_year: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AssignTeacherRequest(BaseModel):
    teacher_id: str


class AddStudentsRequest(BaseModel):
    student_ids: list[str]


