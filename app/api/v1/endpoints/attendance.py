from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import date, datetime
from app.models.attendance import (
    AttendanceCreate, AttendanceUpdate, AttendanceResponse,
    BulkAttendanceCreate, AttendanceStatus
)
from app.core.supabase import supabase, supabase_admin, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.core.logging_config import get_logger
from app.core.exceptions import (
    DatabaseError,
    NotFoundError,
    ValidationError,
    ConflictError,
    sanitize_error_message
)

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def mark_attendance(
    attendance_data: AttendanceCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Mark attendance for a user with validation and duplicate prevention"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        attendance_record = attendance_data.model_dump()
        attendance_record["marked_by"] = current_user["sub"]
        
        # Date validation is done in the model, but double-check
        attendance_date = attendance_record["date"]
        today = date.today()
        if isinstance(attendance_date, str):
            attendance_date = datetime.fromisoformat(attendance_date).date()
        
        if attendance_date > today:
            raise ValidationError(
                f"Attendance date cannot be in the future. Date: {attendance_date}",
                error_code="FUTURE_DATE_NOT_ALLOWED"
            )
        
        # Check for duplicate attendance (same user, same date)
        duplicate_check = db.table("attendance").select("id").eq("user_id", attendance_record["user_id"])\
            .eq("date", attendance_record["date"].isoformat() if hasattr(attendance_record["date"], "isoformat") else str(attendance_record["date"]))\
            .execute()
        
        if duplicate_check.data:
            raise ConflictError(
                f"Attendance already marked for user {attendance_record['user_id']} on date {attendance_record['date']}",
                error_code="DUPLICATE_ATTENDANCE"
            )
        
        # For teachers, validate they can mark attendance for this user (their class)
        if user_role == "teacher":
            # Check if user is a student in one of teacher's classes
            student_check = db.table("students").select("class_id").eq("user_id", attendance_record["user_id"]).single().execute()
            if student_check.data:
                student_class_id = student_check.data.get("class_id")
                teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
                if teacher_check.data:
                    teacher_id = teacher_check.data["id"]
                    class_check = db.table("classes").select("teacher_id").eq("id", student_class_id).single().execute()
                    if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                        raise ValidationError(
                            "You can only mark attendance for students in your assigned classes",
                            error_code="UNAUTHORIZED_CLASS_ACCESS"
                        )
            else:
                # User is not a student, allow for teachers/admins
                pass
        
        # Convert date to string for database
        if hasattr(attendance_record["date"], "isoformat"):
            attendance_record["date"] = attendance_record["date"].isoformat()
        
        logger.info(f"Marking attendance: user={attendance_record['user_id']}, date={attendance_record['date']}, status={attendance_record['status']}")
        response = db.table("attendance").insert(attendance_record).execute()
        
        if not response.data:
            raise DatabaseError("Failed to create attendance record", error_code="ATTENDANCE_CREATE_FAILED")
        
        logger.info(f"Attendance marked successfully: {response.data[0].get('id')}")
        return AttendanceResponse(**response.data[0])
        
    except (ValidationError, ConflictError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to mark attendance: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to mark attendance: {error_message}", error_code="ATTENDANCE_CREATE_ERROR")


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def mark_bulk_attendance(
    bulk_data: BulkAttendanceCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Mark attendance for multiple users at once with validation"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        marked_by = current_user["sub"]
        today = date.today()
        attendances_to_insert = []
        errors = []
        
        # Get teacher's class IDs if teacher
        teacher_class_ids = None
        if user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                classes_response = db.table("classes").select("id").eq("teacher_id", teacher_id).execute()
                teacher_class_ids = [cls["id"] for cls in classes_response.data]
        
        for idx, attendance in enumerate(bulk_data.attendances):
            try:
                att_dict = attendance.model_dump()
                att_dict["marked_by"] = marked_by
                
                # Date validation
                att_date = att_dict["date"]
                if isinstance(att_date, str):
                    att_date = datetime.fromisoformat(att_date).date()
                elif hasattr(att_date, "date"):
                    att_date = att_date.date()
                
                if att_date > today:
                    errors.append(f"Record {idx + 1}: Date cannot be in the future")
                    continue
                
                # Convert to string for storage
                if hasattr(att_dict["date"], "isoformat"):
                    att_dict["date"] = att_dict["date"].isoformat()
                elif isinstance(att_dict["date"], date):
                    att_dict["date"] = att_dict["date"].isoformat()
                
                # Check for duplicates
                duplicate_check = db.table("attendance").select("id").eq("user_id", att_dict["user_id"])\
                    .eq("date", att_dict["date"])\
                    .execute()
                
                if duplicate_check.data:
                    errors.append(f"Record {idx + 1}: Duplicate attendance already exists")
                    continue
                
                # For teachers, validate user belongs to their class
                if user_role == "teacher" and teacher_class_ids:
                    student_check = db.table("students").select("class_id").eq("user_id", att_dict["user_id"]).single().execute()
                    if student_check.data:
                        student_class_id = student_check.data.get("class_id")
                        if student_class_id not in teacher_class_ids:
                            errors.append(f"Record {idx + 1}: Student not in your assigned classes")
                            continue
                
                attendances_to_insert.append(att_dict)
                
            except Exception as e:
                errors.append(f"Record {idx + 1}: {str(e)}")
                continue
        
        if not attendances_to_insert:
            raise ValidationError(
                f"No valid attendance records to insert. Errors: {'; '.join(errors[:5])}",
                error_code="NO_VALID_ATTENDANCE"
            )
        
        # Insert all valid records
        logger.info(f"Bulk marking attendance for {len(attendances_to_insert)} users")
        response = db.table("attendance").insert(attendances_to_insert).execute()
        
        result = {
            "message": f"Marked attendance for {len(response.data)} users",
            "records": response.data,
            "success_count": len(response.data),
            "total_count": len(bulk_data.attendances),
            "errors": errors if errors else None
        }
        
        logger.info(f"Bulk attendance marking completed: {result['success_count']}/{result['total_count']} successful")
        return result
        
    except ValidationError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to mark bulk attendance: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to mark bulk attendance: {error_message}", error_code="BULK_ATTENDANCE_CREATE_ERROR")


@router.get("", response_model=list[AttendanceResponse])
async def list_attendance(
    user_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[AttendanceStatus] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List attendance records with optional filters and proper RLS enforcement"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        query = db.table("attendance").select("*")
        
        # For teachers, restrict to their class students
        if user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                classes_response = db.table("classes").select("id").eq("teacher_id", teacher_id).execute()
                teacher_class_ids = [cls["id"] for cls in classes_response.data]
                
                if teacher_class_ids:
                    # Get student user_ids from teacher's classes
                    students_response = db.table("students").select("user_id").in_("class_id", teacher_class_ids).execute()
                    student_user_ids = [std["user_id"] for std in students_response.data]
                    
                    if student_user_ids:
                        query = query.in_("user_id", student_user_ids)
                    else:
                        # No students in teacher's classes
                        return []
                else:
                    # Teacher has no classes
                    return []
        
        # For students, restrict to their own attendance only
        elif user_role == "student":
            if user_id and user_id != current_user["sub"]:
                # Requesting another user's attendance - not allowed
                return []
            
            query = query.eq("user_id", current_user["sub"])
        
        # Apply filters
        if user_id and user_role != "student":
            query = query.eq("user_id", user_id)
        
        if date_from:
            query = query.gte("date", date_from)
        
        if date_to:
            query = query.lte("date", date_to)
        
        if status:
            query = query.eq("status", status.value)
        
        query = query.order("date", desc=True).range(offset, offset + limit - 1)
        response = query.execute()
        
        logger.debug(f"Retrieved {len(response.data)} attendance records for user {current_user.get('sub')} (role: {user_role})")
        return [AttendanceResponse(**record) for record in response.data]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch attendance: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch attendance: {error_message}", error_code="ATTENDANCE_FETCH_ERROR")


@router.get("/me", response_model=list[AttendanceResponse])
async def get_my_attendance(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: dict = Depends(require_role(["student", "teacher"]))
):
    """Get current user's attendance history with proper RLS enforcement"""
    try:
        user_id = current_user["sub"]
        # Use RLS-enabled client for non-admin users
        db = get_request_scoped_client(
            current_user.get("access_token"),
            False,  # Not admin
            current_user.get("supabase_token")
        )
        
        # RLS will automatically filter to this user's attendance
        query = db.table("attendance").select("*").eq("user_id", user_id)
        
        if date_from:
            date_from_str = date_from.isoformat() if hasattr(date_from, "isoformat") else str(date_from)
            query = query.gte("date", date_from_str)
        
        if date_to:
            date_to_str = date_to.isoformat() if hasattr(date_to, "isoformat") else str(date_to)
            query = query.lte("date", date_to_str)
        
        query = query.order("date", desc=True)
        response = query.execute()
        
        logger.debug(f"Retrieved {len(response.data)} attendance records for user {user_id}")
        return [AttendanceResponse(**record) for record in response.data]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user attendance: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch attendance: {error_message}", error_code="ATTENDANCE_FETCH_ERROR")


@router.get("/{attendance_id}", response_model=AttendanceResponse)
async def get_attendance(
    attendance_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get attendance record by ID with proper RLS enforcement"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        response = db.table("attendance").select("*").eq("id", attendance_id).single().execute()
        
        if not response.data:
            raise NotFoundError(f"Attendance record with ID {attendance_id} not found", error_code="ATTENDANCE_NOT_FOUND")
        
        attendance = response.data
        
        # For students, verify they can access this attendance
        if user_role == "student":
            if attendance.get("user_id") != current_user["sub"]:
                raise NotFoundError("Attendance record not found", error_code="ATTENDANCE_NOT_FOUND")
        
        # For teachers, verify they can access this attendance (their class)
        elif user_role == "teacher":
            user_id = attendance.get("user_id")
            student_check = db.table("students").select("class_id").eq("user_id", user_id).single().execute()
            if student_check.data:
                student_class_id = student_check.data.get("class_id")
                teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
                if teacher_check.data:
                    teacher_id = teacher_check.data["id"]
                    class_check = db.table("classes").select("teacher_id").eq("id", student_class_id).single().execute()
                    if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                        raise NotFoundError("Attendance record not found", error_code="ATTENDANCE_NOT_FOUND")
        
        return AttendanceResponse(**attendance)
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch attendance {attendance_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch attendance: {error_message}", error_code="ATTENDANCE_FETCH_ERROR")


@router.put("/{attendance_id}", response_model=AttendanceResponse)
async def update_attendance(
    attendance_id: str,
    attendance_data: AttendanceUpdate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Update attendance record with validation"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Get existing attendance record
        existing = db.table("attendance").select("*").eq("id", attendance_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Attendance record with ID {attendance_id} not found", error_code="ATTENDANCE_NOT_FOUND")
        
        existing_record = existing.data[0]
        
        # For teachers, validate they can update this attendance
        if user_role == "teacher":
            user_id = existing_record.get("user_id")
            student_check = db.table("students").select("class_id").eq("user_id", user_id).single().execute()
            if student_check.data:
                student_class_id = student_check.data.get("class_id")
                teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
                if teacher_check.data:
                    teacher_id = teacher_check.data["id"]
                    class_check = db.table("classes").select("teacher_id").eq("id", student_class_id).single().execute()
                    if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                        raise ValidationError(
                            "You can only update attendance for students in your assigned classes",
                            error_code="UNAUTHORIZED_CLASS_ACCESS"
                        )
        
        update_data = attendance_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise ValidationError("No data provided for update", error_code="NO_UPDATE_DATA")
        
        logger.info(f"Updating attendance {attendance_id}: {update_data}")
        response = db.table("attendance").update(update_data).eq("id", attendance_id).execute()
        
        if not response.data:
            raise DatabaseError("Failed to update attendance", error_code="ATTENDANCE_UPDATE_FAILED")
        
        logger.info(f"Attendance updated successfully: {attendance_id}")
        return AttendanceResponse(**response.data[0])
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update attendance {attendance_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update attendance: {error_message}", error_code="ATTENDANCE_UPDATE_ERROR")


@router.delete("/{attendance_id}")
async def delete_attendance(
    attendance_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete attendance record"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            True,  # Admin/Principal can delete
            current_user.get("supabase_token")
        )
        
        # Check if attendance exists
        existing = db.table("attendance").select("id").eq("id", attendance_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Attendance record with ID {attendance_id} not found", error_code="ATTENDANCE_NOT_FOUND")
        
        db.table("attendance").delete().eq("id", attendance_id).execute()
        
        logger.info(f"Attendance deleted successfully: {attendance_id}")
        return {"message": "Attendance record deleted successfully"}
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete attendance {attendance_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to delete attendance: {error_message}", error_code="ATTENDANCE_DELETE_ERROR")


@router.get("/stats/{user_id}", response_model=dict)
async def get_attendance_statistics(
    user_id: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get attendance statistics for a user (percentage, counts)"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # For students, they can only view their own stats
        if user_role == "student":
            if user_id != current_user["sub"]:
                raise ValidationError("You can only view your own attendance statistics", error_code="UNAUTHORIZED_ACCESS")
        
        # For teachers, validate user is in their class
        elif user_role == "teacher":
            student_check = db.table("students").select("class_id").eq("user_id", user_id).single().execute()
            if student_check.data:
                student_class_id = student_check.data.get("class_id")
                teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
                if teacher_check.data:
                    teacher_id = teacher_check.data["id"]
                    class_check = db.table("classes").select("teacher_id").eq("id", student_class_id).single().execute()
                    if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                        raise ValidationError(
                            "You can only view statistics for students in your assigned classes",
                            error_code="UNAUTHORIZED_CLASS_ACCESS"
                        )
        
        # Build query
        query = db.table("attendance").select("*").eq("user_id", user_id)
        
        if date_from:
            query = query.gte("date", date_from)
        
        if date_to:
            query = query.lte("date", date_to)
        
        response = query.execute()
        
        # Calculate statistics
        total_records = len(response.data)
        present_count = sum(1 for r in response.data if r.get("status") == "present")
        absent_count = sum(1 for r in response.data if r.get("status") == "absent")
        late_count = sum(1 for r in response.data if r.get("status") == "late")
        excused_count = sum(1 for r in response.data if r.get("status") == "excused")
        
        attendance_percentage = (present_count / total_records * 100) if total_records > 0 else 0
        
        stats = {
            "user_id": user_id,
            "date_from": date_from,
            "date_to": date_to,
            "total_records": total_records,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "excused": excused_count,
            "attendance_percentage": round(attendance_percentage, 2)
        }
        
        logger.debug(f"Retrieved attendance statistics for user {user_id}: {stats}")
        return stats
        
    except ValidationError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch attendance statistics for user {user_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch attendance statistics: {error_message}", error_code="ATTENDANCE_STATS_ERROR")


@router.get("/stats/class/{class_id}", response_model=dict)
async def get_class_attendance_statistics(
    class_id: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Get attendance statistics for a class"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # For teachers, validate they can access this class
        if user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                class_check = db.table("classes").select("teacher_id").eq("id", class_id).single().execute()
                if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                    raise ValidationError(
                        "You can only view statistics for your assigned classes",
                        error_code="UNAUTHORIZED_CLASS_ACCESS"
                    )
        
        # Get all students in the class
        students_response = db.table("students").select("user_id").eq("class_id", class_id).execute()
        student_user_ids = [std["user_id"] for std in students_response.data]
        
        if not student_user_ids:
            return {
                "class_id": class_id,
                "total_students": 0,
                "date_from": date_from,
                "date_to": date_to,
                "statistics": []
            }
        
        # Get attendance for all students
        query = db.table("attendance").select("*").in_("user_id", student_user_ids)
        
        if date_from:
            query = query.gte("date", date_from)
        
        if date_to:
            query = query.lte("date", date_to)
        
        response = query.execute()
        
        # Calculate statistics per student
        student_stats = {}
        for record in response.data:
            uid = record.get("user_id")
            if uid not in student_stats:
                student_stats[uid] = {
                    "user_id": uid,
                    "present": 0,
                    "absent": 0,
                    "late": 0,
                    "excused": 0,
                    "total": 0
                }
            
            status = record.get("status")
            student_stats[uid]["total"] += 1
            if status in student_stats[uid]:
                student_stats[uid][status] += 1
        
        # Calculate percentages
        statistics = []
        for uid, stats in student_stats.items():
            total = stats["total"]
            attendance_pct = (stats["present"] / total * 100) if total > 0 else 0
            statistics.append({
                **stats,
                "attendance_percentage": round(attendance_pct, 2)
            })
        
        result = {
            "class_id": class_id,
            "total_students": len(student_user_ids),
            "date_from": date_from,
            "date_to": date_to,
            "statistics": statistics
        }
        
        logger.debug(f"Retrieved class attendance statistics for class {class_id}")
        return result
        
    except ValidationError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch class attendance statistics for class {class_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch class attendance statistics: {error_message}", error_code="CLASS_ATTENDANCE_STATS_ERROR")




