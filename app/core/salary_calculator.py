"""Centralized Salary Calculation Engine for Teachers"""
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from calendar import monthrange
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SalaryCalculationResult:
    """Result of a salary calculation with detailed breakdown"""
    def __init__(self):
        self.basic_salary: float = 0.0
        self.per_day_salary: float = 0.0
        self.total_working_days: int = 0
        self.present_days: int = 0
        self.absent_days: int = 0
        self.half_days: int = 0
        self.late_days: int = 0
        self.total_deductions: float = 0.0
        self.deductions_by_rule: Dict[str, float] = {}
        self.bonuses: float = 0.0
        self.allowances: float = 0.0
        self.net_salary: float = 0.0
        self.calculation_details: Dict = {}
        self.attendance_summary: Dict = {}

    def to_dict(self) -> Dict:
        """Convert result to dictionary"""
        return {
            "basic_salary": self.basic_salary,
            "per_day_salary": self.per_day_salary,
            "total_working_days": self.total_working_days,
            "present_days": self.present_days,
            "absent_days": self.absent_days,
            "half_days": self.half_days,
            "late_days": self.late_days,
            "total_deductions": self.total_deductions,
            "deductions_by_rule": self.deductions_by_rule,
            "bonuses": self.bonuses,
            "allowances": self.allowances,
            "net_salary": self.net_salary,
            "calculation_details": self.calculation_details,
            "attendance_summary": self.attendance_summary
        }


class SalaryCalculator:
    """Centralized salary calculation engine"""
    
    def __init__(self, db_client):
        """
        Initialize calculator with database client
        
        Args:
            db_client: Supabase client instance
        """
        self.db = db_client
    
    def calculate_working_days(self, month: int, year: int, exclude_weekends: bool = True) -> int:
        """
        Calculate total working days in a month
        
        Args:
            month: Month (1-12)
            year: Year
            exclude_weekends: Whether to exclude weekends (Saturday, Sunday)
        
        Returns:
            Number of working days
        """
        _, days_in_month = monthrange(year, month)
        
        if not exclude_weekends:
            return days_in_month
        
        working_days = 0
        for day in range(1, days_in_month + 1):
            weekday = date(year, month, day).weekday()
            # 5 = Saturday, 6 = Sunday
            if weekday < 5:
                working_days += 1
        
        return working_days
    
    def get_attendance_records(
        self,
        teacher_id: str,
        month: int,
        year: int,
        use_biometric: bool = True,
        fallback_to_regular: bool = True
    ) -> List[Dict]:
        """
        Get attendance records for a teacher for a specific month
        Prioritizes biometric attendance, falls back to regular attendance if enabled
        
        Args:
            teacher_id: Teacher ID
            month: Month (1-12)
            year: Year
            use_biometric: Whether to use biometric attendance
            fallback_to_regular: Whether to fallback to regular attendance if biometric not available
        
        Returns:
            List of attendance records
        """
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        records = []
        
        # Try biometric attendance first
        if use_biometric:
            try:
                # Get teacher's user_id first
                teacher_response = self.db.table("teachers").select("user_id").eq("id", teacher_id).single().execute()
                if teacher_response.data:
                    # Get biometric attendance
                    bio_response = self.db.table("biometric_attendance").select("*")\
                        .eq("teacher_id", teacher_id)\
                        .gte("attendance_date", start_date.isoformat())\
                        .lt("attendance_date", end_date.isoformat())\
                        .execute()
                    
                    if bio_response.data:
                        records = bio_response.data
                        logger.debug(f"Found {len(records)} biometric attendance records for teacher {teacher_id}")
                        return records
            except Exception as e:
                logger.warning(f"Error fetching biometric attendance: {e}")
        
        # Fallback to regular attendance
        if fallback_to_regular and not records:
            try:
                # Get teacher's user_id
                teacher_response = self.db.table("teachers").select("user_id").eq("id", teacher_id).single().execute()
                if teacher_response.data:
                    user_id = teacher_response.data["user_id"]
                    
                    # Get regular attendance
                    reg_response = self.db.table("attendance").select("*")\
                        .eq("user_id", user_id)\
                        .gte("date", start_date.isoformat())\
                        .lt("date", end_date.isoformat())\
                        .execute()
                    
                    if reg_response.data:
                        # Convert regular attendance to biometric-like format
                        records = []
                        for att in reg_response.data:
                            status = att.get("status", "absent")
                            # Map regular attendance status to biometric format
                            bio_status = status
                            if status == "excused":
                                bio_status = "present"  # Excused counts as present for salary
                            
                            records.append({
                                "attendance_date": att.get("date"),
                                "status": bio_status,
                                "deduction_amount": 0.0,
                                "deduction_reason": None,
                                "late_minutes": 0,
                                "early_departure_minutes": 0
                            })
                        
                        logger.debug(f"Found {len(records)} regular attendance records for teacher {teacher_id} (fallback)")
            except Exception as e:
                logger.warning(f"Error fetching regular attendance: {e}")
        
        return records
    
    def get_deduction_rules(self, active_only: bool = True) -> List[Dict]:
        """
        Get attendance deduction rules
        
        Args:
            active_only: Whether to return only active rules
        
        Returns:
            List of deduction rules
        """
        try:
            query = self.db.table("attendance_rules").select("*")
            if active_only:
                query = query.eq("is_active", True)
            
            response = query.order("created_at", desc=False).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching deduction rules: {e}")
            return []
    
    def apply_deduction_rules(
        self,
        attendance_records: List[Dict],
        per_day_salary: float,
        deduction_rules: List[Dict]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Apply deduction rules to attendance records
        
        Args:
            attendance_records: List of attendance records
            per_day_salary: Per day salary amount
            deduction_rules: List of deduction rules
        
        Returns:
            Tuple of (total_deductions, deductions_by_rule)
        """
        total_deductions = 0.0
        deductions_by_rule: Dict[str, float] = {}
        
        # Group rules by type for easier lookup
        rules_by_type: Dict[str, List[Dict]] = {}
        for rule in deduction_rules:
            rule_type = rule.get("rule_type")
            if rule_type:
                if rule_type not in rules_by_type:
                    rules_by_type[rule_type] = []
                rules_by_type[rule_type].append(rule)
        
        # Process each attendance record
        for record in attendance_records:
            status = record.get("status", "absent")
            deduction_amount = float(record.get("deduction_amount", 0)) or 0
            deduction_reason = record.get("deduction_reason")
            
            # If deduction already calculated (from biometric), use it
            if deduction_amount > 0 and deduction_reason:
                total_deductions += deduction_amount
                rule_name = deduction_reason.split(":")[0] if ":" in deduction_reason else "Manual"
                if rule_name not in deductions_by_rule:
                    deductions_by_rule[rule_name] = 0.0
                deductions_by_rule[rule_name] += deduction_amount
                continue
            
            # Apply rules based on status
            if status == "absent":
                # Apply absent rule
                if "absent" in rules_by_type:
                    for rule in rules_by_type["absent"]:
                        deduction = self._calculate_deduction(rule, per_day_salary, "full_day")
                        total_deductions += deduction
                        rule_name = rule.get("rule_name", "Absent")
                        if rule_name not in deductions_by_rule:
                            deductions_by_rule[rule_name] = 0.0
                        deductions_by_rule[rule_name] += deduction
            
            elif status == "half_day":
                # Apply half day rule
                if "half_day" in rules_by_type:
                    for rule in rules_by_type["half_day"]:
                        deduction = self._calculate_deduction(rule, per_day_salary, "half_day")
                        total_deductions += deduction
                        rule_name = rule.get("rule_name", "Half Day")
                        if rule_name not in deductions_by_rule:
                            deductions_by_rule[rule_name] = 0.0
                        deductions_by_rule[rule_name] += deduction
                else:
                    # Default: deduct half day salary
                    deduction = per_day_salary / 2
                    total_deductions += deduction
                    if "Half Day (Default)" not in deductions_by_rule:
                        deductions_by_rule["Half Day (Default)"] = 0.0
                    deductions_by_rule["Half Day (Default)"] += deduction
            
            elif status == "late":
                # Apply late coming rule
                late_minutes = int(record.get("late_minutes", 0))
                if "late_coming" in rules_by_type:
                    for rule in rules_by_type["late_coming"]:
                        grace_minutes = int(rule.get("grace_minutes", 0))
                        max_late_count = int(rule.get("max_late_count", 3))
                        
                        # Check if late exceeds grace period
                        if late_minutes > grace_minutes:
                            # Count how many late days this month
                            late_count = sum(1 for r in attendance_records 
                                           if r.get("status") == "late" and 
                                           int(r.get("late_minutes", 0)) > grace_minutes)
                            
                            # Apply deduction only if exceeds max_late_count
                            if late_count > max_late_count:
                                deduction = self._calculate_deduction(rule, per_day_salary, "late")
                                total_deductions += deduction
                                rule_name = rule.get("rule_name", "Late Coming")
                                if rule_name not in deductions_by_rule:
                                    deductions_by_rule[rule_name] = 0.0
                                deductions_by_rule[rule_name] += deduction
            
            elif status == "early_departure":
                # Apply early departure rule
                if "early_departure" in rules_by_type:
                    for rule in rules_by_type["early_departure"]:
                        deduction = self._calculate_deduction(rule, per_day_salary, "early_departure")
                        total_deductions += deduction
                        rule_name = rule.get("rule_name", "Early Departure")
                        if rule_name not in deductions_by_rule:
                            deductions_by_rule[rule_name] = 0.0
                        deductions_by_rule[rule_name] += deduction
        
        return total_deductions, deductions_by_rule
    
    def _calculate_deduction(self, rule: Dict, per_day_salary: float, context: str) -> float:
        """
        Calculate deduction amount based on rule
        
        Args:
            rule: Deduction rule
            per_day_salary: Per day salary
            context: Context (full_day, half_day, late, etc.)
        
        Returns:
            Deduction amount
        """
        deduction_type = rule.get("deduction_type")
        deduction_value = float(rule.get("deduction_value", 0))
        
        if deduction_type == "percentage":
            return (deduction_value / 100) * per_day_salary
        elif deduction_type == "fixed_amount":
            return deduction_value
        elif deduction_type == "full_day":
            return per_day_salary
        elif deduction_type == "half_day":
            return per_day_salary / 2
        else:
            return 0.0
    
    def calculate_salary(
        self,
        teacher_id: str,
        month: int,
        year: int,
        basic_salary: Optional[float] = None,
        per_day_salary: Optional[float] = None,
        bonuses: float = 0.0,
        allowances: float = 0.0,
        use_biometric: bool = True,
        fallback_to_regular: bool = True
    ) -> SalaryCalculationResult:
        """
        Calculate salary for a teacher for a specific month
        
        Args:
            teacher_id: Teacher ID
            month: Month (1-12)
            year: Year
            basic_salary: Basic monthly salary (if None, fetch from config)
            per_day_salary: Per day salary (if None, calculate from basic_salary)
            bonuses: Additional bonuses
            allowances: Additional allowances
            use_biometric: Whether to use biometric attendance
            fallback_to_regular: Whether to fallback to regular attendance
        
        Returns:
            SalaryCalculationResult with detailed breakdown
        """
        result = SalaryCalculationResult()
        
        try:
            # Get salary configuration if not provided
            if basic_salary is None or per_day_salary is None:
                config_response = self.db.table("teacher_salary_config")\
                    .select("*")\
                    .eq("teacher_id", teacher_id)\
                    .eq("is_active", True)\
                    .execute()
                
                if not config_response.data:
                    raise ValueError(f"No active salary configuration found for teacher {teacher_id}")
                
                config = config_response.data[0]
                result.basic_salary = float(config.get("basic_monthly_salary", 0))
                result.per_day_salary = float(config.get("per_day_salary", 0))
            else:
                result.basic_salary = basic_salary
                result.per_day_salary = per_day_salary
            
            # Calculate per day salary if not provided
            if result.per_day_salary == 0:
                result.total_working_days = self.calculate_working_days(month, year)
                result.per_day_salary = result.basic_salary / result.total_working_days if result.total_working_days > 0 else 0
            else:
                result.total_working_days = self.calculate_working_days(month, year)
            
            # Get attendance records
            attendance_records = self.get_attendance_records(
                teacher_id, month, year, use_biometric, fallback_to_regular
            )
            
            # Count attendance days
            result.present_days = sum(1 for r in attendance_records if r.get("status") == "present")
            result.absent_days = sum(1 for r in attendance_records if r.get("status") == "absent")
            result.half_days = sum(1 for r in attendance_records if r.get("status") == "half_day")
            result.late_days = sum(1 for r in attendance_records if r.get("status") == "late")
            
            # Get deduction rules
            deduction_rules = self.get_deduction_rules(active_only=True)
            
            # Apply deduction rules
            result.total_deductions, result.deductions_by_rule = self.apply_deduction_rules(
                attendance_records, result.per_day_salary, deduction_rules
            )
            
            # Apply bonuses and allowances
            result.bonuses = bonuses
            result.allowances = allowances
            
            # Calculate net salary
            result.net_salary = result.basic_salary - result.total_deductions + result.bonuses + result.allowances
            
            # Build calculation details
            result.calculation_details = {
                "attendance_records_count": len(attendance_records),
                "deduction_rules_applied": len(deduction_rules),
                "deductions_by_rule": result.deductions_by_rule,
                "attendance_summary": {
                    "present": result.present_days,
                    "absent": result.absent_days,
                    "half_day": result.half_days,
                    "late": result.late_days,
                    "total_attendance_days": len(attendance_records)
                }
            }
            
            result.attendance_summary = {
                "present": result.present_days,
                "absent": result.absent_days,
                "half_day": result.half_days,
                "late": result.late_days,
                "total_attendance_days": len(attendance_records),
                "attendance_percentage": (
                    (result.present_days / result.total_working_days * 100) 
                    if result.total_working_days > 0 else 0
                )
            }
            
            logger.info(
                f"Salary calculated for teacher {teacher_id}, month {month}/{year}: "
                f"Basic={result.basic_salary}, Deductions={result.total_deductions}, "
                f"Net={result.net_salary}"
            )
            
        except Exception as e:
            logger.exception(f"Error calculating salary for teacher {teacher_id}: {e}")
            raise
        
        return result








