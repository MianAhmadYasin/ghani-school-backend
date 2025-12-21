"""Financial Reporting Utilities"""
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from calendar import monthrange
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class FinancialReportGenerator:
    """Generate financial reports for different periods"""
    
    def __init__(self, db_client):
        """
        Initialize report generator with database client
        
        Args:
            db_client: Supabase client instance
        """
        self.db = db_client
    
    def get_date_range(self, report_type: str, date_from: Optional[str] = None, date_to: Optional[str] = None) -> tuple[date, date]:
        """
        Get date range for report type
        
        Args:
            report_type: daily, weekly, monthly, 6-month, yearly, custom
            date_from: Start date for custom reports
            date_to: End date for custom reports
        
        Returns:
            Tuple of (start_date, end_date)
        """
        today = date.today()
        
        if report_type == "daily":
            return today, today
        
        elif report_type == "weekly":
            # Start of week (Monday)
            days_since_monday = today.weekday()
            start_date = today - timedelta(days=days_since_monday)
            return start_date, today
        
        elif report_type == "monthly":
            # Current month
            start_date = date(today.year, today.month, 1)
            _, last_day = monthrange(today.year, today.month)
            end_date = date(today.year, today.month, last_day)
            return start_date, end_date
        
        elif report_type == "6-month":
            # Last 6 months
            end_date = today
            # Go back 6 months
            if today.month > 6:
                start_date = date(today.year, today.month - 5, 1)
            else:
                start_date = date(today.year - 1, today.month + 7, 1)
            return start_date, end_date
        
        elif report_type == "yearly":
            # Current year
            start_date = date(today.year, 1, 1)
            end_date = date(today.year, 12, 31)
            return start_date, end_date
        
        elif report_type == "custom":
            if not date_from or not date_to:
                raise ValueError("date_from and date_to are required for custom reports")
            return date.fromisoformat(date_from), date.fromisoformat(date_to)
        
        else:
            raise ValueError(f"Invalid report type: {report_type}")
    
    def get_previous_period(self, report_type: str, current_start: date, current_end: date) -> tuple[date, date]:
        """Get previous period for comparison"""
        period_days = (current_end - current_start).days + 1
        
        prev_end = current_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        
        return prev_start, prev_end
    
    def aggregate_financial_data(self, start_date: date, end_date: date) -> Dict:
        """
        Aggregate all financial data for a date range
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Dictionary with aggregated financial data
        """
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        
        # Get donations (income)
        donations_response = self.db.table("donations")\
            .select("*")\
            .gte("date", start_str)\
            .lte("date", end_str)\
            .execute()
        
        donations = donations_response.data or []
        total_income = sum(float(d.get("amount", 0)) for d in donations)
        income_breakdown = {}
        for donation in donations:
            purpose = donation.get("purpose", "General")
            amount = float(donation.get("amount", 0))
            income_breakdown[purpose] = income_breakdown.get(purpose, 0) + amount
        
        # Get expenses
        expenses_response = self.db.table("expenses")\
            .select("*")\
            .gte("date", start_str)\
            .lte("date", end_str)\
            .execute()
        
        expenses = expenses_response.data or []
        total_expenses = sum(float(e.get("amount", 0)) for e in expenses)
        expense_breakdown = {}
        for expense in expenses:
            category = expense.get("category", "Other")
            amount = float(expense.get("amount", 0))
            expense_breakdown[category] = expense_breakdown.get(category, 0) + amount
        
        # Get salaries from monthly_salary_calculations (paid salaries)
        # Note: This gets calculated salaries, not necessarily paid
        # We'll use salary_records table for actual paid salaries
        salary_records_response = self.db.table("salary_records")\
            .select("*")\
            .gte("paid_date", start_str)\
            .lte("paid_date", end_str)\
            .execute()
        
        salary_records = salary_records_response.data or []
        total_salaries = sum(float(s.get("net_salary", 0)) for s in salary_records)
        
        # Also get from monthly_salary_calculations for months in range
        calc_salaries = 0
        salary_breakdown = {}
        
        # Get calculations for months in the date range
        current_date = start_date
        while current_date <= end_date:
            month = current_date.month
            year = current_date.year
            
            calc_response = self.db.table("monthly_salary_calculations")\
                .select("*")\
                .eq("calculation_month", month)\
                .eq("calculation_year", year)\
                .eq("is_approved", True)\
                .execute()
            
            for calc in (calc_response.data or []):
                calc_salaries += float(calc.get("net_salary", 0))
                # Get teacher name for breakdown
                teacher_id = calc.get("teacher_id")
                if teacher_id:
                    teacher_response = self.db.table("teachers")\
                        .select("user:full_name")\
                        .eq("id", teacher_id)\
                        .single()\
                        .execute()
                    teacher_name = "Unknown"
                    if teacher_response.data:
                        user = teacher_response.data.get("user")
                        teacher_name = user.get("full_name", "Unknown") if user else "Unknown"
                    
                    salary_breakdown[teacher_name] = salary_breakdown.get(teacher_name, 0) + float(calc.get("net_salary", 0))
            
            # Move to next month
            if month == 12:
                current_date = date(year + 1, 1, 1)
            else:
                current_date = date(year, month + 1, 1)
        
        # Use calculated salaries if salary_records not available
        if total_salaries == 0:
            total_salaries = calc_salaries
        
        # Get stationery costs (from distributions)
        distributions_response = self.db.table("stationery_distributions")\
            .select("*")\
            .gte("distributed_date", start_str)\
            .lte("distributed_date", end_str)\
            .execute()
        
        distributions = distributions_response.data or []
        # Calculate stationery costs (assuming average price per unit)
        # In real implementation, you'd look up actual item prices
        total_stationery = len(distributions) * 10  # Placeholder calculation
        
        # Calculate net profit/loss
        net_profit_loss = total_income - total_expenses - total_salaries - total_stationery
        
        return {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total_salaries": total_salaries,
            "total_stationery": total_stationery,
            "net_profit_loss": net_profit_loss,
            "income_breakdown": income_breakdown,
            "expense_breakdown": expense_breakdown,
            "salary_breakdown": salary_breakdown,
            "donations_count": len(donations),
            "expenses_count": len(expenses),
            "salary_records_count": len(salary_records)
        }
    
    def generate_report(
        self,
        report_type: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_comparison: bool = True
    ) -> Dict:
        """
        Generate financial report
        
        Args:
            report_type: daily, weekly, monthly, 6-month, yearly, custom
            date_from: Start date for custom reports
            date_to: End date for custom reports
            include_comparison: Whether to include comparison with previous period
        
        Returns:
            FinancialSummary dictionary
        """
        # Get date range
        start_date, end_date = self.get_date_range(report_type, date_from, date_to)
        
        # Aggregate current period data
        current_data = self.aggregate_financial_data(start_date, end_date)
        
        # Get previous period for comparison
        comparison = None
        if include_comparison:
            try:
                prev_start, prev_end = self.get_previous_period(report_type, start_date, end_date)
                prev_data = self.aggregate_financial_data(prev_start, prev_end)
                
                comparison = {
                    "previous_period_start": prev_start.isoformat(),
                    "previous_period_end": prev_end.isoformat(),
                    "income_change": current_data["total_income"] - prev_data["total_income"],
                    "income_change_percent": (
                        ((current_data["total_income"] - prev_data["total_income"]) / prev_data["total_income"] * 100)
                        if prev_data["total_income"] > 0 else 0
                    ),
                    "expenses_change": current_data["total_expenses"] - prev_data["total_expenses"],
                    "expenses_change_percent": (
                        ((current_data["total_expenses"] - prev_data["total_expenses"]) / prev_data["total_expenses"] * 100)
                        if prev_data["total_expenses"] > 0 else 0
                    ),
                    "net_change": current_data["net_profit_loss"] - prev_data["net_profit_loss"],
                    "net_change_percent": (
                        ((current_data["net_profit_loss"] - prev_data["net_profit_loss"]) / abs(prev_data["net_profit_loss"]) * 100)
                        if prev_data["net_profit_loss"] != 0 else 0
                    )
                }
            except Exception as e:
                logger.warning(f"Could not generate comparison: {e}")
        
        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_income": round(current_data["total_income"], 2),
            "total_expenses": round(current_data["total_expenses"], 2),
            "total_salaries": round(current_data["total_salaries"], 2),
            "total_stationery": round(current_data["total_stationery"], 2),
            "net_profit_loss": round(current_data["net_profit_loss"], 2),
            "income_breakdown": {k: round(v, 2) for k, v in current_data["income_breakdown"].items()},
            "expense_breakdown": {k: round(v, 2) for k, v in current_data["expense_breakdown"].items()},
            "salary_breakdown": {k: round(v, 2) for k, v in current_data["salary_breakdown"].items()},
            "comparison": comparison
        }








