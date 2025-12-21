from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File
from typing import Optional, List
import csv
import io
import base64
from datetime import datetime, date, time, timedelta
from app.models.attendance_salary import (
    SchoolTimingCreate, SchoolTimingUpdate, SchoolTimingResponse,
    AttendanceRuleCreate, AttendanceRuleUpdate, AttendanceRuleResponse,
    BiometricAttendanceCreate, BiometricAttendanceUpdate, BiometricAttendanceResponse,
    CSVUploadHistoryCreate, CSVUploadHistoryResponse,
    MonthlySalaryCalculationCreate, MonthlySalaryCalculationUpdate, MonthlySalaryCalculationResponse,
    TeacherSalaryConfigCreate, TeacherSalaryConfigUpdate, TeacherSalaryConfigResponse,
    CSVUploadRequest, AttendanceSummary, SalaryCalculationRequest
)
from app.core.supabase import supabase, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.core.salary_calculator import SalaryCalculator
from app.core.logging_config import get_logger
from app.core.exceptions import (
    DatabaseError,
    NotFoundError,
    ValidationError,
    sanitize_error_message
)

logger = get_logger(__name__)
router = APIRouter()


# ==================== School Timings ====================

@router.get("/timings", response_model=List[SchoolTimingResponse])
async def get_school_timings(
    current_user: dict = Depends(get_current_user)
):
    """Get school timing configurations"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        response = db.table("school_timings").select("*").order("created_at", desc=True).execute()
        return [SchoolTimingResponse(**timing) for timing in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/timings", response_model=SchoolTimingResponse, status_code=status.HTTP_201_CREATED)
async def create_school_timing(
    timing_data: SchoolTimingCreate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Create new school timing configuration"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        response = db.table("school_timings").insert(timing_data.model_dump()).execute()
        return SchoolTimingResponse(**response.data[0])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/timings/{timing_id}", response_model=SchoolTimingResponse)
async def update_school_timing(
    timing_id: str,
    timing_data: SchoolTimingUpdate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Update school timing configuration"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        existing = db.table("school_timings").select("*").eq("id", timing_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timing configuration not found")
        
        update_data = {k: v for k, v in timing_data.model_dump().items() if v is not None}
        response = db.table("school_timings").update(update_data).eq("id", timing_id).execute()
        
        return SchoolTimingResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Attendance Rules ====================

@router.get("/rules", response_model=List[AttendanceRuleResponse])
async def get_attendance_rules(
    current_user: dict = Depends(get_current_user)
):
    """Get attendance deduction rules"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        response = db.table("attendance_rules").select("*").order("created_at", desc=True).execute()
        return [AttendanceRuleResponse(**rule) for rule in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/rules", response_model=AttendanceRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_attendance_rule(
    rule_data: AttendanceRuleCreate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Create new attendance rule with validation"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Validate rule data
        rule_dict = rule_data.model_dump()
        
        # Validate deduction type and value
        deduction_type = rule_dict.get("deduction_type")
        deduction_value = float(rule_dict.get("deduction_value", 0))
        
        if deduction_type == "percentage" and not (0 <= deduction_value <= 100):
            raise ValidationError("Percentage deduction must be between 0 and 100", error_code="INVALID_DEDUCTION_VALUE")
        elif deduction_type == "fixed_amount" and deduction_value < 0:
            raise ValidationError("Fixed amount deduction cannot be negative", error_code="INVALID_DEDUCTION_VALUE")
        
        response = db.table("attendance_rules").insert(rule_dict).execute()
        
        if not response.data:
            raise DatabaseError("Failed to create attendance rule", error_code="RULE_CREATE_FAILED")
        
        logger.info(f"Created attendance rule: {rule_dict.get('rule_name')}")
        return AttendanceRuleResponse(**response.data[0])
        
    except (ValidationError, DatabaseError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create attendance rule: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create attendance rule: {error_message}", error_code="RULE_CREATE_ERROR")


@router.put("/rules/{rule_id}", response_model=AttendanceRuleResponse)
async def update_attendance_rule(
    rule_id: str,
    rule_data: AttendanceRuleUpdate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Update attendance rule"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        existing = db.table("attendance_rules").select("*").eq("id", rule_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance rule not found")
        
        update_data = {k: v for k, v in rule_data.model_dump().items() if v is not None}
        response = db.table("attendance_rules").update(update_data).eq("id", rule_id).execute()
        
        return AttendanceRuleResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== CSV Upload ====================

@router.post("/upload-csv", response_model=CSVUploadHistoryResponse, status_code=status.HTTP_201_CREATED)
async def upload_biometric_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Upload biometric attendance CSV file"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Create upload history record
        upload_record = {
            "file_name": file.filename,
            "file_size": len(content),
            "upload_status": "processing",
            "uploaded_by": current_user["sub"]
        }
        
        upload_response = db.table("csv_upload_history").insert(upload_record).execute()
        upload_id = upload_response.data[0]["id"]
        
        # Parse CSV and process attendance records
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        records_processed = 0
        records_successful = 0
        records_failed = 0
        error_log = []
        
        # Get active school timings
        timings_response = db.table("school_timings").select("*").eq("is_active", True).execute()
        active_timing = timings_response.data[0] if timings_response.data else None
        
        # Get active attendance rules
        rules_response = db.table("attendance_rules").select("*").eq("is_active", True).execute()
        active_rules = {rule["rule_type"]: rule for rule in rules_response.data}
        
        for row in csv_reader:
            records_processed += 1
            try:
                # Extract data from CSV row (adjust column names as needed)
                teacher_name = row.get('Name', '').strip()
                check_in_time = row.get('Time', '').strip()
                attendance_date = row.get('Date', '').strip()
                status = row.get('Status', '').strip()
                
                # Find teacher by name
                teacher_response = db.table("teachers").select("id").ilike("user.full_name", f"%{teacher_name}%").execute()
                if not teacher_response.data:
                    error_log.append(f"Teacher not found: {teacher_name}")
                    records_failed += 1
                    continue
                
                teacher_id = teacher_response.data[0]["id"]
                
                # Parse date and time
                try:
                    parsed_date = datetime.strptime(attendance_date, "%A, %B %d, %Y").date()
                    parsed_time = datetime.strptime(check_in_time, "%I:%M:%S %p").time()
                except ValueError:
                    error_log.append(f"Invalid date/time format for {teacher_name}: {attendance_date}, {check_in_time}")
                    records_failed += 1
                    continue
                
                # Determine attendance status and calculate deductions
                attendance_status = "present"
                deduction_amount = 0
                deduction_reason = ""
                late_minutes = 0
                
                if active_timing and status == "C/In":
                    arrival_time = datetime.strptime(active_timing["arrival_time"], "%H:%M:%S").time()
                    grace_time = datetime.combine(date.today(), arrival_time) + timedelta(minutes=active_timing["grace_period_minutes"])
                    
                    if parsed_time > grace_time.time():
                        late_minutes = int((datetime.combine(date.today(), parsed_time) - datetime.combine(date.today(), arrival_time)).total_seconds() / 60)
                        attendance_status = "late"
                        
                        # Apply late coming rule
                        if "late_coming" in active_rules:
                            rule = active_rules["late_coming"]
                            if rule["deduction_type"] == "percentage":
                                deduction_amount = rule["deduction_value"] * 100  # Assuming per_day_salary is 100
                            elif rule["deduction_type"] == "fixed_amount":
                                deduction_amount = rule["deduction_value"]
                            deduction_reason = f"Late arrival: {late_minutes} minutes"
                
                # Create or update biometric attendance record
                attendance_record = {
                    "teacher_id": teacher_id,
                    "attendance_date": parsed_date.isoformat(),
                    "check_in_time": parsed_time.isoformat() if status == "C/In" else None,
                    "status": attendance_status,
                    "late_minutes": late_minutes,
                    "deduction_amount": deduction_amount,
                    "deduction_reason": deduction_reason,
                    "uploaded_file_id": upload_id
                }
                
                # Check if record already exists
                existing = db.table("biometric_attendance").select("*").eq("teacher_id", teacher_id).eq("attendance_date", parsed_date.isoformat()).execute()
                
                if existing.data:
                    # Update existing record
                    db.table("biometric_attendance").update(attendance_record).eq("id", existing.data[0]["id"]).execute()
                else:
                    # Create new record
                    db.table("biometric_attendance").insert(attendance_record).execute()
                
                records_successful += 1
                
            except Exception as e:
                error_log.append(f"Error processing row {records_processed}: {str(e)}")
                records_failed += 1
        
        # Update upload history
        final_status = "completed" if records_failed == 0 else "partial" if records_successful > 0 else "failed"
        db.table("csv_upload_history").update({
            "records_processed": records_processed,
            "records_successful": records_successful,
            "records_failed": records_failed,
            "upload_status": final_status,
            "error_log": "\n".join(error_log) if error_log else None
        }).eq("id", upload_id).execute()
        
        return CSVUploadHistoryResponse(**upload_response.data[0])
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Biometric Attendance ====================

@router.get("/biometric", response_model=List[BiometricAttendanceResponse])
async def get_biometric_attendance(
    teacher_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get biometric attendance records"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        query = db.table("biometric_attendance").select("*")
        
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        if date_from:
            query = query.gte("attendance_date", date_from)
        if date_to:
            query = query.lte("attendance_date", date_to)
        
        response = query.order("attendance_date", desc=True).execute()
        return [BiometricAttendanceResponse(**record) for record in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/summary", response_model=List[AttendanceSummary])
async def get_attendance_summary(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get attendance summary for teachers"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        
        # Get all teachers
        teachers_response = db.table("teachers").select("id, user(full_name)").execute()
        
        summaries = []
        for teacher in teachers_response.data:
            teacher_id = teacher["id"]
            teacher_name = teacher["user"]["full_name"] if teacher["user"] else "Unknown"
            
            # Build query for attendance records
            query = db.table("biometric_attendance").select("*").eq("teacher_id", teacher_id)
            
            if month and year:
                # Filter by month and year
                start_date = f"{year}-{month:02d}-01"
                if month == 12:
                    end_date = f"{year + 1}-01-01"
                else:
                    end_date = f"{year}-{month + 1:02d}-01"
                query = query.gte("attendance_date", start_date).lt("attendance_date", end_date)
            
            attendance_response = query.execute()
            records = attendance_response.data
            
            # Calculate summary
            total_days = len(records)
            present_days = len([r for r in records if r["status"] == "present"])
            absent_days = len([r for r in records if r["status"] == "absent"])
            half_days = len([r for r in records if r["status"] == "half_day"])
            late_days = len([r for r in records if r["status"] == "late"])
            total_deductions = sum(float(r["deduction_amount"]) for r in records)
            
            attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
            
            summaries.append(AttendanceSummary(
                teacher_id=teacher_id,
                teacher_name=teacher_name,
                total_days=total_days,
                present_days=present_days,
                absent_days=absent_days,
                half_days=half_days,
                late_days=late_days,
                attendance_percentage=round(attendance_percentage, 2),
                total_deductions=total_deductions
            ))
        
        return summaries
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Salary Calculations ====================

@router.post("/calculate-salary", response_model=List[MonthlySalaryCalculationResponse])
async def calculate_monthly_salary(
    calculation_request: SalaryCalculationRequest,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Calculate monthly salary for teachers based on attendance using enhanced calculator"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        calculator = SalaryCalculator(db)
        
        month = calculation_request.month
        year = calculation_request.year
        teacher_ids = calculation_request.teacher_ids
        
        # Validate month and year
        if not (1 <= month <= 12):
            raise ValidationError("Month must be between 1 and 12", error_code="INVALID_MONTH")
        
        # Get teachers to calculate for
        if teacher_ids:
            teachers_response = db.table("teachers").select("id").in_("id", teacher_ids).execute()
        else:
            teachers_response = db.table("teachers").select("id").execute()
        
        if not teachers_response.data:
            raise NotFoundError("No teachers found", error_code="NO_TEACHERS")
        
        calculations = []
        errors = []
        
        for teacher in teachers_response.data:
            teacher_id = teacher["id"]
            
            try:
                # Calculate salary using the calculator
                result = calculator.calculate_salary(
                    teacher_id=teacher_id,
                    month=month,
                    year=year,
                    use_biometric=True,
                    fallback_to_regular=True
                )
                
                # Create calculation record
                calculation_data = {
                    "teacher_id": teacher_id,
                    "calculation_month": month,
                    "calculation_year": year,
                    "basic_salary": result.basic_salary,
                    "per_day_salary": result.per_day_salary,
                    "total_working_days": result.total_working_days,
                    "present_days": result.present_days,
                    "absent_days": result.absent_days,
                    "half_days": result.half_days,
                    "late_days": result.late_days,
                    "total_deductions": result.total_deductions,
                    "net_salary": result.net_salary,
                    "calculation_details": result.calculation_details
                }
                
                # Check if calculation already exists
                existing = db.table("monthly_salary_calculations").select("*")\
                    .eq("teacher_id", teacher_id)\
                    .eq("calculation_month", month)\
                    .eq("calculation_year", year)\
                    .execute()
                
                if existing.data:
                    # Update existing calculation
                    response = db.table("monthly_salary_calculations")\
                        .update(calculation_data)\
                        .eq("id", existing.data[0]["id"])\
                        .execute()
                else:
                    # Create new calculation
                    response = db.table("monthly_salary_calculations")\
                        .insert(calculation_data)\
                        .execute()
                
                if response.data:
                    calculations.append(MonthlySalaryCalculationResponse(**response.data[0]))
                    
            except ValueError as e:
                # Skip teacher if no salary config, but log it
                errors.append(f"Teacher {teacher_id}: {str(e)}")
                logger.warning(f"Skipping teacher {teacher_id}: {str(e)}")
                continue
            except Exception as e:
                errors.append(f"Teacher {teacher_id}: {str(e)}")
                logger.error(f"Error calculating salary for teacher {teacher_id}: {str(e)}")
                continue
        
        if not calculations:
            raise ValidationError(
                f"No salaries calculated. Errors: {'; '.join(errors[:5])}",
                error_code="NO_CALCULATIONS"
            )
        
        logger.info(f"Calculated salaries for {len(calculations)} teachers for {month}/{year}")
        return calculations
        
    except (ValidationError, NotFoundError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to calculate salaries: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to calculate salaries: {error_message}", error_code="SALARY_CALCULATION_ERROR")


@router.post("/preview-salary", response_model=dict)
async def preview_salary_calculation(
    teacher_id: str,
    month: int,
    year: int,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Preview salary calculation without saving"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        calculator = SalaryCalculator(db)
        
        # Validate inputs
        if not (1 <= month <= 12):
            raise ValidationError("Month must be between 1 and 12", error_code="INVALID_MONTH")
        
        # Calculate salary (preview mode - doesn't save)
        result = calculator.calculate_salary(
            teacher_id=teacher_id,
            month=month,
            year=year,
            use_biometric=True,
            fallback_to_regular=True
        )
        
        return result.to_dict()
        
    except (ValidationError, ValueError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to preview salary: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to preview salary: {error_message}", error_code="SALARY_PREVIEW_ERROR")


@router.post("/recalculate-salary/{calculation_id}", response_model=MonthlySalaryCalculationResponse)
async def recalculate_salary(
    calculation_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Recalculate an existing salary calculation (for corrections)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        calculator = SalaryCalculator(db)
        
        # Get existing calculation
        existing = db.table("monthly_salary_calculations").select("*").eq("id", calculation_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Salary calculation {calculation_id} not found", error_code="CALCULATION_NOT_FOUND")
        
        calc = existing.data
        teacher_id = calc["teacher_id"]
        month = calc["calculation_month"]
        year = calc["calculation_year"]
        
        # Recalculate
        result = calculator.calculate_salary(
            teacher_id=teacher_id,
            month=month,
            year=year,
            use_biometric=True,
            fallback_to_regular=True
        )
        
        # Update calculation
        calculation_data = {
            "basic_salary": result.basic_salary,
            "per_day_salary": result.per_day_salary,
            "total_working_days": result.total_working_days,
            "present_days": result.present_days,
            "absent_days": result.absent_days,
            "half_days": result.half_days,
            "late_days": result.late_days,
            "total_deductions": result.total_deductions,
            "net_salary": result.net_salary,
            "calculation_details": result.calculation_details,
            "is_approved": False  # Reset approval on recalculation
        }
        
        response = db.table("monthly_salary_calculations")\
            .update(calculation_data)\
            .eq("id", calculation_id)\
            .execute()
        
        if not response.data:
            raise DatabaseError("Failed to update calculation", error_code="UPDATE_FAILED")
        
        logger.info(f"Recalculated salary {calculation_id}")
        return MonthlySalaryCalculationResponse(**response.data[0])
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to recalculate salary: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to recalculate salary: {error_message}", error_code="SALARY_RECALCULATION_ERROR")


@router.get("/salary-calculations", response_model=List[MonthlySalaryCalculationResponse])
async def get_salary_calculations(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    teacher_id: Optional[str] = Query(None),
    is_approved: Optional[bool] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get salary calculation records with filtering"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        query = db.table("monthly_salary_calculations").select("*")
        
        # For teachers, only show their own calculations
        if user_role == "teacher":
            teacher_check = db.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                query = query.eq("teacher_id", teacher_check.data["id"])
            else:
                return []  # Teacher record not found
        
        if month:
            query = query.eq("calculation_month", month)
        if year:
            query = query.eq("calculation_year", year)
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        if is_approved is not None:
            query = query.eq("is_approved", is_approved)
        
        response = query.order("calculation_year", desc=True).order("calculation_month", desc=True).execute()
        return [MonthlySalaryCalculationResponse(**calc) for calc in response.data]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch salary calculations: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch salary calculations: {error_message}", error_code="CALCULATIONS_FETCH_ERROR")


@router.post("/salary-calculations/{calculation_id}/approve", response_model=MonthlySalaryCalculationResponse)
async def approve_salary_calculation(
    calculation_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Approve a salary calculation"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Get calculation
        existing = db.table("monthly_salary_calculations").select("*").eq("id", calculation_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Salary calculation {calculation_id} not found", error_code="CALCULATION_NOT_FOUND")
        
        # Update approval status
        response = db.table("monthly_salary_calculations")\
            .update({
                "is_approved": True,
                "approved_by": current_user["sub"],
                "approved_at": datetime.utcnow().isoformat()
            })\
            .eq("id", calculation_id)\
            .execute()
        
        if not response.data:
            raise DatabaseError("Failed to approve calculation", error_code="APPROVAL_FAILED")
        
        logger.info(f"Salary calculation {calculation_id} approved by {current_user.get('sub')}")
        return MonthlySalaryCalculationResponse(**response.data[0])
        
    except (NotFoundError, DatabaseError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to approve salary calculation: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to approve calculation: {error_message}", error_code="APPROVAL_ERROR")


@router.post("/salary-calculations/bulk-approve", response_model=dict)
async def bulk_approve_salary_calculations(
    calculation_ids: List[str],
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Bulk approve multiple salary calculations"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        approved_count = 0
        errors = []
        
        for calc_id in calculation_ids:
            try:
                # Get calculation
                existing = db.table("monthly_salary_calculations").select("*").eq("id", calc_id).single().execute()
                if not existing.data:
                    errors.append(f"Calculation {calc_id} not found")
                    continue
                
                # Update approval status
                response = db.table("monthly_salary_calculations")\
                    .update({
                        "is_approved": True,
                        "approved_by": current_user["sub"],
                        "approved_at": datetime.utcnow().isoformat()
                    })\
                    .eq("id", calc_id)\
                    .execute()
                
                if response.data:
                    approved_count += 1
                else:
                    errors.append(f"Failed to approve {calc_id}")
                    
            except Exception as e:
                errors.append(f"Error approving {calc_id}: {str(e)}")
                continue
        
        return {
            "approved_count": approved_count,
            "total_count": len(calculation_ids),
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to bulk approve calculations: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to bulk approve: {error_message}", error_code="BULK_APPROVAL_ERROR")


# ==================== Teacher Salary Configuration ====================

@router.get("/teacher-salary-config", response_model=List[TeacherSalaryConfigResponse])
async def get_teacher_salary_config(
    teacher_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get teacher salary configurations"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        query = db.table("teacher_salary_config").select("*")
        
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        
        response = query.order("effective_from", desc=True).execute()
        return [TeacherSalaryConfigResponse(**config) for config in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/teacher-salary-config", response_model=TeacherSalaryConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_teacher_salary_config(
    config_data: TeacherSalaryConfigCreate,
    adjustment_reason: Optional[str] = None,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create teacher salary configuration with history tracking"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        config_dict = config_data.model_dump()
        
        # Validate salary amounts
        basic_salary = float(config_dict.get("basic_monthly_salary", 0))
        per_day_salary = float(config_dict.get("per_day_salary", 0))
        
        if basic_salary < 0:
            raise ValidationError("Basic salary cannot be negative", error_code="INVALID_SALARY")
        if per_day_salary < 0:
            raise ValidationError("Per day salary cannot be negative", error_code="INVALID_SALARY")
        
        # Deactivate existing active configs for this teacher
        existing_configs = db.table("teacher_salary_config")\
            .select("*")\
            .eq("teacher_id", config_dict["teacher_id"])\
            .eq("is_active", True)\
            .execute()
        
        if existing_configs.data:
            # Set effective_to date for old configs
            effective_from = config_dict.get("effective_from")
            for old_config in existing_configs.data:
                db.table("teacher_salary_config")\
                    .update({"is_active": False, "effective_to": effective_from})\
                    .eq("id", old_config["id"])\
                    .execute()
        
        # Create new config
        if adjustment_reason:
            # Store adjustment reason in a separate audit table if needed
            # For now, we'll log it
            logger.info(f"Salary config created for teacher {config_dict['teacher_id']}: {adjustment_reason}")
        
        response = db.table("teacher_salary_config").insert(config_dict).execute()
        
        if not response.data:
            raise DatabaseError("Failed to create salary configuration", error_code="CONFIG_CREATE_FAILED")
        
        logger.info(f"Created salary config for teacher {config_dict['teacher_id']}")
        return TeacherSalaryConfigResponse(**response.data[0])
        
    except (ValidationError, DatabaseError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create salary config: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create salary config: {error_message}", error_code="CONFIG_CREATE_ERROR")


@router.put("/teacher-salary-config/{config_id}", response_model=TeacherSalaryConfigResponse)
async def update_teacher_salary_config(
    config_id: str,
    config_data: TeacherSalaryConfigUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update teacher salary configuration"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        existing = db.table("teacher_salary_config").select("*").eq("id", config_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary configuration not found")
        
        update_data = {k: v for k, v in config_data.model_dump().items() if v is not None}
        response = db.table("teacher_salary_config").update(update_data).eq("id", config_id).execute()
        
        return TeacherSalaryConfigResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== CSV Upload History ====================

@router.get("/upload-history", response_model=List[CSVUploadHistoryResponse])
async def get_upload_history(
    current_user: dict = Depends(get_current_user)
):
    """Get CSV upload history"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        response = db.table("csv_upload_history").select("*").order("upload_date", desc=True).execute()
        return [CSVUploadHistoryResponse(**history) for history in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



