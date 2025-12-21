from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List, Union
from datetime import date, datetime
from app.models.user import UserResponse


class SalaryInfo(BaseModel):
    basic_salary: float
    allowances: Optional[float] = 0.0
    currency: str = "USD"


class TeacherBase(BaseModel):
    employee_id: str
    join_date: date
    qualification: str
    subjects: List[str]
    salary_info: SalaryInfo
    status: str = "active"


class TeacherCreate(BaseModel):
    # User info
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    
    # Teacher specific
    employee_id: str
    join_date: Union[date, str]  # Accept both date object and ISO string
    qualification: str
    
    @field_validator('join_date', mode='before')
    @classmethod
    def parse_join_date(cls, v):
        """Parse join_date from string or date object"""
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00')).date()
            except (ValueError, AttributeError):
                try:
                    return datetime.strptime(v, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")
        return v
    subjects: List[str]
    salary_info: SalaryInfo
    cnic_number: Optional[str] = None
    experience_years: Optional[int] = 0
    contact_number: Optional[str] = None
    home_address: Optional[str] = None
    cnic_copy_url: Optional[str] = None
    degree_copy_url: Optional[str] = None
    remarks: Optional[str] = None


class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    qualification: Optional[str] = None
    subjects: Optional[List[str]] = None
    salary_info: Optional[SalaryInfo] = None
    status: Optional[str] = None
    cnic_number: Optional[str] = None
    experience_years: Optional[int] = None
    contact_number: Optional[str] = None
    home_address: Optional[str] = None
    cnic_copy_url: Optional[str] = None
    degree_copy_url: Optional[str] = None
    remarks: Optional[str] = None


class TeacherResponse(BaseModel):
    id: str
    user_id: str
    employee_id: str
    join_date: date
    qualification: str
    subjects: List[str]
    salary_info: SalaryInfo
    status: str
    created_at: datetime
    cnic_number: Optional[str] = None
    experience_years: Optional[int] = 0
    contact_number: Optional[str] = None
    home_address: Optional[str] = None
    cnic_copy_url: Optional[str] = None
    degree_copy_url: Optional[str] = None
    remarks: Optional[str] = None
    user: Optional[UserResponse] = None
    
    model_config = ConfigDict(from_attributes=True)


