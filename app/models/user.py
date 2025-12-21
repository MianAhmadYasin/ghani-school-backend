from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    PRINCIPAL = "principal"
    TEACHER = "teacher"
    STUDENT = "student"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# Base schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    phone: Optional[str] = None
    address: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: str
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


