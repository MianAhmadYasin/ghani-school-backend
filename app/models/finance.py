from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ==================== Stationery Items ====================

class StationeryItemBase(BaseModel):
    name: str
    category: str
    quantity: int
    unit: str
    reorder_level: int = 10


class StationeryItemCreate(StationeryItemBase):
    pass


class StationeryItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[int] = None
    unit: Optional[str] = None
    reorder_level: Optional[int] = None


class StationeryItemResponse(StationeryItemBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Stationery Distributions ====================

class StationeryDistributionBase(BaseModel):
    student_id: str
    item_id: str
    quantity: int
    distributed_date: str  # Accept string in YYYY-MM-DD format


class StationeryDistributionCreate(StationeryDistributionBase):
    pass


class StationeryDistributionResponse(StationeryDistributionBase):
    id: str
    distributed_by: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Salary Records ====================

class SalaryRecordBase(BaseModel):
    teacher_id: str
    month: int
    year: int
    basic_salary: float
    deductions: float = 0.0
    bonuses: float = 0.0
    paid_date: Optional[str] = None  # Accept string in YYYY-MM-DD format


class SalaryRecordCreate(SalaryRecordBase):
    pass


class SalaryRecordUpdate(BaseModel):
    deductions: Optional[float] = None
    bonuses: Optional[float] = None
    paid_date: Optional[str] = None  # Accept string in YYYY-MM-DD format


class SalaryRecordResponse(SalaryRecordBase):
    id: str
    net_salary: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Expenses ====================

class ExpenseBase(BaseModel):
    category: str
    amount: float
    description: str
    date: str  # Accept string in YYYY-MM-DD format
    payment_method: Optional[str] = None


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    category: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    date: Optional[str] = None  # Accept string in YYYY-MM-DD format
    payment_method: Optional[str] = None


class ExpenseResponse(ExpenseBase):
    id: str
    recorded_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Donations ====================

class DonationBase(BaseModel):
    donor_name: str
    amount: float
    date: str  # Accept string in YYYY-MM-DD format
    purpose: Optional[str] = None
    receipt_number: str
    payment_method: Optional[str] = None


class DonationCreate(DonationBase):
    pass


class DonationUpdate(BaseModel):
    donor_name: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[str] = None  # Accept string in YYYY-MM-DD format
    purpose: Optional[str] = None
    receipt_number: Optional[str] = None
    payment_method: Optional[str] = None


class DonationResponse(DonationBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Invoices ====================

class InvoiceItem(BaseModel):
    """Invoice line item"""
    description: str
    quantity: float = 1.0
    unit_price: float
    amount: float
    category: Optional[str] = None


class InvoiceBase(BaseModel):
    teacher_id: str
    calculation_id: str
    month: int
    year: int
    invoice_date: str  # YYYY-MM-DD format
    due_date: Optional[str] = None  # YYYY-MM-DD format
    status: str = "draft"  # draft, sent, paid, overdue
    items: List[InvoiceItem]  # Line items (basic salary, deductions, bonuses, etc.)
    subtotal: float
    deductions: float = 0.0
    bonuses: float = 0.0
    tax: float = 0.0
    net_amount: float
    total_amount: float
    notes: Optional[str] = None


class InvoiceCreate(BaseModel):
    calculation_id: str
    invoice_date: Optional[str] = None  # If None, use current date
    due_date: Optional[str] = None  # If None, calculate from invoice_date
    template: str = "detailed"  # simple or detailed
    notes: Optional[str] = None


class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


class InvoiceResponse(InvoiceBase):
    id: str
    invoice_number: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Financial Reports ====================

class FinancialSummary(BaseModel):
    """Financial summary for a period"""
    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    total_income: float
    total_expenses: float
    total_salaries: float
    total_stationery: float
    net_profit_loss: float
    income_breakdown: Dict[str, float]  # Category breakdown
    expense_breakdown: Dict[str, float]  # Category breakdown
    salary_breakdown: Dict[str, float]  # Per teacher or summary
    comparison: Optional[Dict[str, Any]] = None  # Comparison with previous period


class FinancialReportRequest(BaseModel):
    """Request parameters for financial report"""
    report_type: str  # daily, weekly, monthly, 6-month, yearly, custom
    date_from: Optional[str] = None  # YYYY-MM-DD, required for custom
    date_to: Optional[str] = None  # YYYY-MM-DD, required for custom
    format: str = "json"  # json, pdf, excel, csv
    include_charts: bool = True