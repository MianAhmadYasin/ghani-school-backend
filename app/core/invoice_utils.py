"""Invoice generation utilities"""
from datetime import date, datetime, timedelta
from typing import Optional
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def generate_invoice_number(db_client, month: int, year: int) -> str:
    """
    Generate unique invoice number in format: INV-YYYY-MM-XXXXX
    
    Args:
        db_client: Supabase client
        month: Month (1-12)
        year: Year
    
    Returns:
        Invoice number string
    """
    try:
        # Get count of invoices for this month/year
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        # Count existing invoices in this month/year
        response = db_client.table("invoices")\
            .select("invoice_number", count="exact")\
            .gte("invoice_date", start_date)\
            .lt("invoice_date", end_date)\
            .execute()
        
        count = response.count or 0
        
        # Generate sequential number (5 digits, zero-padded)
        sequence_number = count + 1
        invoice_number = f"INV-{year}-{month:02d}-{sequence_number:05d}"
        
        logger.debug(f"Generated invoice number: {invoice_number}")
        return invoice_number
        
    except Exception as e:
        logger.error(f"Error generating invoice number: {e}")
        # Fallback to timestamp-based number
        timestamp = int(datetime.utcnow().timestamp())
        return f"INV-{year}-{month:02d}-{timestamp % 100000:05d}"


def calculate_due_date(invoice_date: date, days: int = 30) -> date:
    """
    Calculate due date from invoice date
    
    Args:
        invoice_date: Invoice date
        days: Number of days to add (default 30)
    
    Returns:
        Due date
    """
    return invoice_date + timedelta(days=days)


def build_invoice_items(calculation: dict, template: str = "detailed") -> list[dict]:
    """
    Build invoice line items from salary calculation
    
    Args:
        calculation: Salary calculation dictionary
        template: Template type (simple or detailed)
    
    Returns:
        List of invoice items
    """
    items = []
    
    basic_salary = float(calculation.get("basic_salary", 0))
    total_deductions = float(calculation.get("total_deductions", 0))
    bonuses = float(calculation.get("bonuses", 0)) if "bonuses" in calculation else 0.0
    
    calculation_details = calculation.get("calculation_details", {})
    deductions_by_rule = calculation_details.get("deductions_by_rule", {})
    
    # Add basic salary item
    items.append({
        "description": "Basic Monthly Salary",
        "quantity": 1.0,
        "unit_price": basic_salary,
        "amount": basic_salary,
        "category": "salary"
    })
    
    if template == "detailed":
        # Add attendance summary
        attendance_summary = calculation_details.get("attendance_summary", {})
        present_days = attendance_summary.get("present", 0)
        absent_days = attendance_summary.get("absent", 0)
        half_days = attendance_summary.get("half_day", 0)
        late_days = attendance_summary.get("late", 0)
        total_days = attendance_summary.get("total_attendance_days", 0)
        
        if total_days > 0:
            items.append({
                "description": f"Attendance: {present_days} Present, {absent_days} Absent, {half_days} Half Day, {late_days} Late",
                "quantity": 1.0,
                "unit_price": 0,
                "amount": 0,
                "category": "attendance"
            })
        
        # Add detailed deductions
        if deductions_by_rule:
            for rule_name, deduction_amount in deductions_by_rule.items():
                if deduction_amount > 0:
                    items.append({
                        "description": f"Deduction: {rule_name}",
                        "quantity": 1.0,
                        "unit_price": -deduction_amount,
                        "amount": -deduction_amount,
                        "category": "deduction"
                    })
        elif total_deductions > 0:
            items.append({
                "description": "Total Deductions",
                "quantity": 1.0,
                "unit_price": -total_deductions,
                "amount": -total_deductions,
                "category": "deduction"
            })
        
        # Add bonuses if any
        if bonuses > 0:
            items.append({
                "description": "Bonuses",
                "quantity": 1.0,
                "unit_price": bonuses,
                "amount": bonuses,
                "category": "bonus"
            })
    else:
        # Simple template - just show total deductions
        if total_deductions > 0:
            items.append({
                "description": "Deductions",
                "quantity": 1.0,
                "unit_price": -total_deductions,
                "amount": -total_deductions,
                "category": "deduction"
            })
        
        if bonuses > 0:
            items.append({
                "description": "Bonuses",
                "quantity": 1.0,
                "unit_price": bonuses,
                "amount": bonuses,
                "category": "bonus"
            })
    
    return items


def validate_invoice_status(status: str) -> bool:
    """Validate invoice status"""
    valid_statuses = ["draft", "sent", "paid", "overdue", "cancelled"]
    return status in valid_statuses


def update_invoice_status_if_overdue(db_client) -> int:
    """
    Update invoice status to overdue if past due date
    Returns count of updated invoices
    """
    try:
        today = date.today()
        
        # Find invoices that are past due and not already paid/cancelled/overdue
        response = db_client.table("invoices")\
            .select("id")\
            .lt("due_date", today.isoformat())\
            .in_("status", ["draft", "sent"])\
            .execute()
        
        updated_count = 0
        for invoice in response.data:
            db_client.table("invoices")\
                .update({"status": "overdue"})\
                .eq("id", invoice["id"])\
                .execute()
            updated_count += 1
        
        if updated_count > 0:
            logger.info(f"Updated {updated_count} invoices to overdue status")
        
        return updated_count
        
    except Exception as e:
        logger.error(f"Error updating overdue invoices: {e}")
        return 0








