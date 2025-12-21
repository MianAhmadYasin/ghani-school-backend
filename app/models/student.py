from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from app.models.user import UserResponse


class GuardianInfo(BaseModel):
    name: str
    relation: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None


class StudentBase(BaseModel):
    admission_number: str
    admission_date: date
    class_id: Optional[str] = None
    guardian_info: GuardianInfo
    status: str = "active"


class StudentCreate(BaseModel):
    # User info
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    
    # Student specific
    admission_number: str
    admission_date: str  # Changed from date to str to handle frontend input
    class_id: Optional[str] = None
    guardian_info: GuardianInfo


class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    class_id: Optional[str] = None
    guardian_info: Optional[GuardianInfo] = None
    status: Optional[str] = None


class StudentResponse(BaseModel):
    id: str
    user_id: str
    admission_number: str
    admission_date: date
    class_id: Optional[str] = None
    guardian_info: GuardianInfo
    status: str
    created_at: datetime
    user: Optional[UserResponse] = None
    
    model_config = ConfigDict(from_attributes=True)


