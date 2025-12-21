from pydantic import BaseModel
from typing import Optional, Literal, Any
from datetime import datetime, date


# ==================== System Settings ====================

class SystemSettingBase(BaseModel):
    setting_key: str
    setting_value: str
    setting_type: Literal['string', 'number', 'boolean', 'json']
    category: Literal['general', 'academic', 'financial', 'security', 'notification', 'appearance']
    description: Optional[str] = None
    is_public: bool = False


class SystemSettingCreate(SystemSettingBase):
    pass


class SystemSettingUpdate(BaseModel):
    setting_value: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class SystemSettingResponse(SystemSettingBase):
    id: str
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== Role Permissions ====================

class RolePermissionBase(BaseModel):
    role: Literal['admin', 'principal', 'teacher', 'student', 'parent']
    permission_key: str
    permission_value: bool = True


class RolePermissionCreate(RolePermissionBase):
    pass


class RolePermissionUpdate(BaseModel):
    permission_value: bool


class RolePermissionResponse(RolePermissionBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Fee Structure ====================

class FeeStructureBase(BaseModel):
    class_level: str
    fee_type: Literal['tuition', 'admission', 'exam', 'library', 'transport', 'activity', 'other']
    amount: float
    currency: str = 'USD'
    academic_year: str
    is_active: bool = True


class FeeStructureCreate(FeeStructureBase):
    pass


class FeeStructureUpdate(BaseModel):
    amount: Optional[float] = None
    is_active: Optional[bool] = None


class FeeStructureResponse(FeeStructureBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Academic Year ====================

class AcademicYearBase(BaseModel):
    year_name: str
    start_date: str  # YYYY-MM-DD format
    end_date: str    # YYYY-MM-DD format
    is_current: bool = False


class AcademicYearCreate(AcademicYearBase):
    pass


class AcademicYearUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None


class AcademicYearResponse(AcademicYearBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Bulk Settings Update ====================

class BulkSettingsUpdate(BaseModel):
    settings: dict[str, str]  # key: value pairs


# ==================== Settings Export ====================

class SettingsExport(BaseModel):
    general: dict[str, Any]
    academic: dict[str, Any]
    financial: dict[str, Any]
    security: dict[str, Any]
    notification: dict[str, Any]
    appearance: dict[str, Any]
    permissions: dict[str, dict[str, bool]]  # role: {permission: value}
    fee_structure: list[FeeStructureResponse]
    academic_years: list[AcademicYearResponse]










