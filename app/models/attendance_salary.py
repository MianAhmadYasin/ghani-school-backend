from pydantic import BaseModel
from typing import Optional, Literal, Any
from datetime import datetime, date, time


# ==================== School Timings ====================

class SchoolTimingBase(BaseModel):
    timing_name: str = 'Default'
    arrival_time: str  # HH:MM:SS format
    departure_time: str  # HH:MM:SS format
    grace_period_minutes: int = 5
    is_active: bool = True


class SchoolTimingCreate(SchoolTimingBase):
    pass


class SchoolTimingUpdate(BaseModel):
    timing_name: Optional[str] = None
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    grace_period_minutes: Optional[int] = None
    is_active: Optional[bool] = None


class SchoolTimingResponse(SchoolTimingBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Attendance Rules ====================

class AttendanceRuleBase(BaseModel):
    rule_name: str
    rule_type: Literal['late_coming', 'half_day', 'absent', 'early_departure']
    condition_description: str
    deduction_type: Literal['percentage', 'fixed_amount', 'full_day', 'half_day']
    deduction_value: float = 0
    grace_minutes: int = 0
    max_late_count: int = 3
    is_active: bool = True


class AttendanceRuleCreate(AttendanceRuleBase):
    pass


class AttendanceRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    condition_description: Optional[str] = None
    deduction_type: Optional[str] = None
    deduction_value: Optional[float] = None
    grace_minutes: Optional[int] = None
    max_late_count: Optional[int] = None
    is_active: Optional[bool] = None


class AttendanceRuleResponse(AttendanceRuleBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Biometric Attendance ====================

class BiometricAttendanceBase(BaseModel):
    teacher_id: str
    attendance_date: str  # YYYY-MM-DD format
    check_in_time: Optional[str] = None  # HH:MM:SS format
    check_out_time: Optional[str] = None  # HH:MM:SS format
    total_hours: float = 0
    status: Literal['present', 'absent', 'half_day', 'late', 'early_departure']
    late_minutes: int = 0
    early_departure_minutes: int = 0
    deduction_amount: float = 0
    deduction_reason: Optional[str] = None
    is_manual_override: bool = False
    override_reason: Optional[str] = None


class BiometricAttendanceCreate(BiometricAttendanceBase):
    pass


class BiometricAttendanceUpdate(BaseModel):
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    total_hours: Optional[float] = None
    status: Optional[str] = None
    late_minutes: Optional[int] = None
    early_departure_minutes: Optional[int] = None
    deduction_amount: Optional[float] = None
    deduction_reason: Optional[str] = None
    is_manual_override: Optional[bool] = None
    override_reason: Optional[str] = None


class BiometricAttendanceResponse(BiometricAttendanceBase):
    id: str
    uploaded_file_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== CSV Upload History ====================

class CSVUploadHistoryBase(BaseModel):
    file_name: str
    file_size: int
    records_processed: int = 0
    records_successful: int = 0
    records_failed: int = 0
    upload_status: Literal['processing', 'completed', 'failed', 'partial']
    error_log: Optional[str] = None


class CSVUploadHistoryCreate(CSVUploadHistoryBase):
    pass


class CSVUploadHistoryResponse(CSVUploadHistoryBase):
    id: str
    upload_date: datetime
    uploaded_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Monthly Salary Calculations ====================

class MonthlySalaryCalculationBase(BaseModel):
    teacher_id: str
    calculation_month: int
    calculation_year: int
    basic_salary: float
    per_day_salary: float
    total_working_days: int
    present_days: int = 0
    absent_days: int = 0
    half_days: int = 0
    late_days: int = 0
    total_deductions: float = 0
    net_salary: float
    calculation_details: Optional[dict] = None
    is_approved: bool = False


class MonthlySalaryCalculationCreate(MonthlySalaryCalculationBase):
    pass


class MonthlySalaryCalculationUpdate(BaseModel):
    is_approved: Optional[bool] = None
    approved_by: Optional[str] = None


class MonthlySalaryCalculationResponse(MonthlySalaryCalculationBase):
    id: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Teacher Salary Configuration ====================

class TeacherSalaryConfigBase(BaseModel):
    teacher_id: str
    basic_monthly_salary: float
    per_day_salary: float
    effective_from: str  # YYYY-MM-DD format
    effective_to: Optional[str] = None  # YYYY-MM-DD format
    is_active: bool = True


class TeacherSalaryConfigCreate(TeacherSalaryConfigBase):
    pass


class TeacherSalaryConfigUpdate(BaseModel):
    basic_monthly_salary: Optional[float] = None
    per_day_salary: Optional[float] = None
    effective_to: Optional[str] = None
    is_active: Optional[bool] = None


class TeacherSalaryConfigResponse(TeacherSalaryConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== CSV Upload Request ====================

class CSVUploadRequest(BaseModel):
    file_name: str
    file_content: str  # Base64 encoded CSV content
    file_size: int


# ==================== Attendance Summary ====================

class AttendanceSummary(BaseModel):
    teacher_id: str
    teacher_name: str
    total_days: int
    present_days: int
    absent_days: int
    half_days: int
    late_days: int
    attendance_percentage: float
    total_deductions: float


# ==================== Salary Calculation Request ====================

class SalaryCalculationRequest(BaseModel):
    month: int
    year: int
    teacher_ids: Optional[list[str]] = None  # If None, calculate for all teachers










