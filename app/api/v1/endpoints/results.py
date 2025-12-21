"""
Exam Results API Endpoints
Supports bulk upload, result management, and validation
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File
from typing import Optional, List
from datetime import datetime
import csv
import io
from app.models.exam import (
    ExamResultCreate, ExamResultUpdate, ExamResultResponse,
    BulkResultUpload, BulkUploadValidation, BulkUploadResponse,
    ResultStatus
)
from app.core.supabase import supabase_admin, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.core.logging_config import get_logger
from app.core.exceptions import (
    DatabaseError,
    NotFoundError,
    ValidationError,
    sanitize_error_message
)
from app.core.grading_utils import calculate_grade, get_active_grading_scheme

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=ExamResultResponse, status_code=status.HTTP_201_CREATED)
async def create_result(
    result_data: ExamResultCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Create a single exam result"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Validate exam exists
        exam_check = db.table("exams").select("id, total_marks, class_id, created_by").eq("id", result_data.exam_id).single().execute()
        if not exam_check.data:
            raise NotFoundError(f"Exam with ID {result_data.exam_id} not found", error_code="EXAM_NOT_FOUND")
        
        exam = exam_check.data
        
        # Validate student exists and belongs to class
        student_check = db.table("students").select("id, class_id, user_id").eq("id", result_data.student_id).single().execute()
        if not student_check.data:
            raise NotFoundError(f"Student with ID {result_data.student_id} not found", error_code="STUDENT_NOT_FOUND")
        
        if student_check.data.get("class_id") != exam.get("class_id"):
            raise ValidationError(
                "Student does not belong to the exam's class",
                error_code="STUDENT_CLASS_MISMATCH"
            )
        
        # For teachers, validate they created the exam
        if user_role == "teacher" and exam.get("created_by") != current_user["sub"]:
            raise ValidationError(
                "You can only add results for exams you created",
                error_code="UNAUTHORIZED_EXAM_ACCESS"
            )
        
        result_record = result_data.model_dump()
        result_record["uploaded_by"] = current_user["sub"]
        result_record["total_marks"] = exam.get("total_marks", result_data.total_marks)
        
        # Auto-calculate grade if not provided
        if not result_record.get("grade"):
            percentage = (result_record["marks_obtained"] / result_record["total_marks"]) * 100
            active_scheme = get_active_grading_scheme(db)
            criteria = active_scheme.get("criteria") if active_scheme else None
            result_record["grade"] = calculate_grade(percentage, criteria=criteria)
        
        # Check for duplicate
        duplicate_check = db.table("exam_results").select("id").eq("exam_id", result_data.exam_id)\
            .eq("student_id", result_data.student_id).execute()
        
        if duplicate_check.data and len(duplicate_check.data) > 0:
            raise ValidationError(
                "Result already exists for this exam and student",
                error_code="DUPLICATE_RESULT"
            )
        
        # Insert result
        logger.info(f"Creating result: exam={result_data.exam_id}, student={result_data.student_id}")
        response = db.table("exam_results").insert(result_record).execute()
        
        if not response.data or len(response.data) == 0:
            raise DatabaseError("Failed to create result record", error_code="RESULT_CREATE_FAILED")
        
        created_result = response.data[0]
        
        # Fetch student and uploader names
        student_profile = db.table("profiles").select("full_name").eq("user_id", student_check.data.get("user_id")).single().execute()
        uploader_profile = db.table("profiles").select("full_name").eq("user_id", current_user["sub"]).single().execute()
        student = db.table("students").select("admission_number").eq("id", result_data.student_id).single().execute()
        
        created_result["student_name"] = student_profile.data.get("full_name") if student_profile.data else None
        created_result["admission_number"] = student.data.get("admission_number") if student.data else None
        created_result["uploaded_by_name"] = uploader_profile.data.get("full_name") if uploader_profile.data else None
        
        logger.info(f"Result created successfully: {created_result.get('id')}")
        return ExamResultResponse(**created_result)
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create result: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create result: {error_message}", error_code="RESULT_CREATE_ERROR")


@router.get("", response_model=List[ExamResultResponse])
async def list_results(
    exam_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    student_id: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List exam results with optional filters"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        query = db.table("exam_results").select("*")
        
        # For students, only show their own results
        if user_role == "student":
            student_check = db.table("students").select("id").eq("user_id", current_user["sub"]).single().execute()
            if student_check.data:
                query = query.eq("student_id", student_check.data["id"])
            else:
                return []
        
        # For teachers, restrict to their exams
        elif user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                classes_response = db.table("classes").select("id").eq("teacher_id", teacher_id).execute()
                teacher_class_ids = [cls["id"] for cls in classes_response.data]
                
                if teacher_class_ids:
                    exams_response = db.table("exams").select("id").in_("class_id", teacher_class_ids).execute()
                    exam_ids = [exam["id"] for exam in exams_response.data]
                    if exam_ids:
                        query = query.in_("exam_id", exam_ids)
                    else:
                        return []
                else:
                    return []
        
        # Apply filters
        if exam_id:
            query = query.eq("exam_id", exam_id)
        if student_id:
            query = query.eq("student_id", student_id)
        if class_id:
            # Filter by class via exam
            exams_response = db.table("exams").select("id").eq("class_id", class_id).execute()
            exam_ids = [exam["id"] for exam in exams_response.data]
            if exam_ids:
                query = query.in_("exam_id", exam_ids)
            else:
                return []
        
        query = query.order("uploaded_at", desc=True)
        
        if limit > 0:
            query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        results_data = response.data or []
        
        # Fetch student and uploader names
        student_ids = list(set(r.get("student_id") for r in results_data if r.get("student_id")))
        uploader_ids = list(set(r.get("uploaded_by") for r in results_data if r.get("uploaded_by")))
        
        students_map = {}
        uploaders_map = {}
        
        if student_ids:
            students_resp = db.table("students").select("id, admission_number, user_id").in_("id", student_ids).execute()
            user_ids = [s.get("user_id") for s in students_resp.data if s.get("user_id")]
            if user_ids:
                profiles_resp = db.table("profiles").select("user_id, full_name").in_("user_id", user_ids).execute()
                profiles_map = {p.get("user_id"): p.get("full_name") for p in profiles_resp.data}
                for student in students_resp.data:
                    students_map[student["id"]] = {
                        "name": profiles_map.get(student.get("user_id")),
                        "admission": student.get("admission_number")
                    }
        
        if uploader_ids:
            uploaders_resp = db.table("profiles").select("user_id, full_name").in_("user_id", uploader_ids).execute()
            uploaders_map = {p.get("user_id"): p.get("full_name") for p in uploaders_resp.data}
        
        for result in results_data:
            student_info = students_map.get(result.get("student_id"), {})
            result["student_name"] = student_info.get("name")
            result["admission_number"] = student_info.get("admission")
            result["uploaded_by_name"] = uploaders_map.get(result.get("uploaded_by"))
        
        return [ExamResultResponse(**result) for result in results_data]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch results: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch results: {error_message}", error_code="RESULT_FETCH_ERROR")


@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_results(
    bulk_data: BulkResultUpload,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Bulk upload exam results"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Validate exam exists
        exam_check = db.table("exams").select("id, total_marks, class_id, created_by").eq("id", bulk_data.exam_id).single().execute()
        if not exam_check.data:
            raise NotFoundError(f"Exam with ID {bulk_data.exam_id} not found", error_code="EXAM_NOT_FOUND")
        
        exam = exam_check.data
        
        # For teachers, validate they created the exam
        if user_role == "teacher" and exam.get("created_by") != current_user["sub"]:
            raise ValidationError(
                "You can only upload results for exams you created",
                error_code="UNAUTHORIZED_EXAM_ACCESS"
            )
        
        # Get all students in the class
        class_students_resp = db.table("students").select("id, admission_number, user_id").eq("class_id", exam.get("class_id")).execute()
        students_by_admission = {s.get("admission_number"): s for s in class_students_resp.data}
        students_by_id = {s.get("id"): s for s in class_students_resp.data}
        
        # Get active grading scheme
        active_scheme = get_active_grading_scheme(db)
        criteria = active_scheme.get("criteria") if active_scheme else None
        total_marks = exam.get("total_marks", 100.0)
        
        results_to_insert = []
        errors = []
        success_count = 0
        
        # Process each result entry
        for idx, entry in enumerate(bulk_data.results):
            try:
                # Find student
                student = None
                if entry.student_id:
                    student = students_by_id.get(entry.student_id)
                elif entry.admission_number:
                    student = students_by_admission.get(entry.admission_number)
                elif entry.student_name:
                    # Try to find by name (less reliable)
                    for s in class_students_resp.data:
                        profile = db.table("profiles").select("full_name").eq("user_id", s.get("user_id")).single().execute()
                        if profile.data and profile.data.get("full_name") == entry.student_name:
                            student = s
                            break
                
                if not student:
                    errors.append({
                        "row": idx + 1,
                        "error": f"Student not found: {entry.admission_number or entry.student_name or entry.student_id}"
                    })
                    continue
                
                # Validate marks
                if entry.marks_obtained < 0 or entry.marks_obtained > total_marks:
                    errors.append({
                        "row": idx + 1,
                        "error": f"Marks ({entry.marks_obtained}) must be between 0 and {total_marks}"
                    })
                    continue
                
                # Check if result already exists
                if not bulk_data.overwrite_existing:
                    existing = db.table("exam_results").select("id").eq("exam_id", bulk_data.exam_id)\
                        .eq("student_id", student["id"]).execute()
                    if existing.data:
                        errors.append({
                            "row": idx + 1,
                            "error": f"Result already exists for student {student.get('admission_number')}"
                        })
                        continue
                
                # Calculate grade
                percentage = (entry.marks_obtained / total_marks) * 100
                grade = calculate_grade(percentage, criteria=criteria) if not entry.remarks else None
                
                result_record = {
                    "exam_id": bulk_data.exam_id,
                    "student_id": student["id"],
                    "marks_obtained": float(entry.marks_obtained),
                    "total_marks": total_marks,
                    "grade": grade,
                    "status": entry.status.value if isinstance(entry.status, ResultStatus) else entry.status,
                    "remarks": entry.remarks,
                    "uploaded_by": current_user["sub"]
                }
                
                results_to_insert.append(result_record)
                success_count += 1
                
            except Exception as e:
                errors.append({
                    "row": idx + 1,
                    "error": str(e)
                })
                continue
        
        if not results_to_insert:
            raise ValidationError(
                "No valid results to upload",
                error_code="NO_VALID_RESULTS"
            )
        
        # Insert results (upsert if overwrite_existing)
        inserted_count = 0
        for result in results_to_insert:
            try:
                if bulk_data.overwrite_existing:
                    # Upsert
                    existing = db.table("exam_results").select("id").eq("exam_id", result["exam_id"])\
                        .eq("student_id", result["student_id"]).execute()
                    if existing.data:
                        db.table("exam_results").update(result).eq("id", existing.data[0]["id"]).execute()
                    else:
                        db.table("exam_results").insert(result).execute()
                else:
                    db.table("exam_results").insert(result).execute()
                inserted_count += 1
            except Exception as e:
                errors.append({
                    "student_id": result["student_id"],
                    "error": f"Failed to insert: {str(e)}"
                })
        
        logger.info(f"Bulk upload completed: {inserted_count} results inserted, {len(errors)} errors")
        
        return BulkUploadResponse(
            success_count=inserted_count,
            error_count=len(errors),
            errors=errors,
            message=f"Successfully uploaded {inserted_count} results. {len(errors)} errors occurred."
        )
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to bulk upload results: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to bulk upload results: {error_message}", error_code="BULK_UPLOAD_ERROR")


@router.post("/validate-upload")
async def validate_upload_file(
    exam_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Validate uploaded CSV/Excel file before import"""
    try:
        # Read file content
        content = await file.read()
        
        # For now, support CSV only (Excel parsing can be added later)
        if not file.filename.endswith('.csv'):
            raise ValidationError("Only CSV files are supported", error_code="INVALID_FILE_TYPE")
        
        # Parse CSV
        csv_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)
        
        # Validate file structure
        required_columns = ['admission_number', 'marks_obtained']
        if not all(col in csv_reader.fieldnames for col in required_columns):
            raise ValidationError(
                f"CSV must contain columns: {', '.join(required_columns)}",
                error_code="INVALID_CSV_STRUCTURE"
            )
        
        # Validate exam exists
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        exam_check = db.table("exams").select("id, total_marks, class_id").eq("id", exam_id).single().execute()
        if not exam_check.data:
            raise NotFoundError(f"Exam with ID {exam_id} not found", error_code="EXAM_NOT_FOUND")
        
        exam = exam_check.data
        total_marks = exam.get("total_marks", 100.0)
        
        # Validate each row
        validation_errors = []
        valid_entries = []
        
        class_students_resp = db.table("students").select("id, admission_number").eq("class_id", exam.get("class_id")).execute()
        students_by_admission = {s.get("admission_number"): s for s in class_students_resp.data}
        
        for idx, row in enumerate(rows, start=2):  # Start at 2 (row 1 is header)
            admission = row.get('admission_number', '').strip()
            marks_str = row.get('marks_obtained', '').strip()
            
            if not admission:
                validation_errors.append({
                    "row": idx,
                    "error": "Admission number is required"
                })
                continue
            
            if not marks_str:
                validation_errors.append({
                    "row": idx,
                    "error": "Marks obtained is required"
                })
                continue
            
            try:
                marks = float(marks_str)
            except ValueError:
                validation_errors.append({
                    "row": idx,
                    "error": f"Invalid marks value: {marks_str}"
                })
                continue
            
            if marks < 0 or marks > total_marks:
                validation_errors.append({
                    "row": idx,
                    "error": f"Marks must be between 0 and {total_marks}"
                })
                continue
            
            if admission not in students_by_admission:
                validation_errors.append({
                    "row": idx,
                    "error": f"Student with admission number '{admission}' not found in class"
                })
                continue
            
            valid_entries.append({
                "admission_number": admission,
                "marks_obtained": marks
            })
        
        return BulkUploadValidation(
            valid=len(validation_errors) == 0,
            errors=validation_errors,
            warnings=[],
            valid_entries=len(valid_entries),
            invalid_entries=len(validation_errors)
        )
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to validate upload: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to validate upload: {error_message}", error_code="VALIDATION_ERROR")


@router.get("/export-template")
async def export_template(
    exam_id: str,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Download CSV template for bulk upload"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Validate exam exists
        exam_check = db.table("exams").select("id, class_id").eq("id", exam_id).single().execute()
        if not exam_check.data:
            raise NotFoundError(f"Exam with ID {exam_id} not found", error_code="EXAM_NOT_FOUND")
        
        # Get students in class
        students_resp = db.table("students").select("admission_number, user_id").eq("class_id", exam_check.data.get("class_id")).execute()
        
        # Get student names
        user_ids = [s.get("user_id") for s in students_resp.data if s.get("user_id")]
        profiles_map = {}
        if user_ids:
            profiles_resp = db.table("profiles").select("user_id, full_name").in_("user_id", user_ids).execute()
            profiles_map = {p.get("user_id"): p.get("full_name") for p in profiles_resp.data}
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['admission_number', 'student_name', 'marks_obtained', 'remarks'])
        
        # Student rows (pre-filled)
        for student in students_resp.data:
            student_name = profiles_map.get(student.get("user_id"), "")
            writer.writerow([
                student.get("admission_number"),
                student_name,
                "",  # Marks to be filled
                ""   # Remarks optional
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        from fastapi.responses import Response
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=exam_results_template_{exam_id}.csv"
            }
        )
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to export template: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to export template: {error_message}", error_code="TEMPLATE_EXPORT_ERROR")


@router.get("/{result_id}", response_model=ExamResultResponse)
async def get_result(
    result_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get result by ID"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        response = db.table("exam_results").select("*").eq("id", result_id).single().execute()
        
        if not response.data:
            raise NotFoundError(f"Result with ID {result_id} not found", error_code="RESULT_NOT_FOUND")
        
        result = response.data
        
        # For students, verify they can access this result
        if user_role == "student":
            student_check = db.table("students").select("id").eq("user_id", current_user["sub"]).single().execute()
            if student_check.data and result.get("student_id") != student_check.data["id"]:
                raise NotFoundError("Result not found", error_code="RESULT_NOT_FOUND")
        
        # Fetch names
        student = db.table("students").select("admission_number, user_id").eq("id", result.get("student_id")).single().execute()
        if student.data:
            profile = db.table("profiles").select("full_name").eq("user_id", student.data.get("user_id")).single().execute()
            result["student_name"] = profile.data.get("full_name") if profile.data else None
            result["admission_number"] = student.data.get("admission_number")
        
        uploader_profile = db.table("profiles").select("full_name").eq("user_id", result.get("uploaded_by")).single().execute()
        result["uploaded_by_name"] = uploader_profile.data.get("full_name") if uploader_profile.data else None
        
        return ExamResultResponse(**result)
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch result {result_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch result: {error_message}", error_code="RESULT_FETCH_ERROR")


@router.put("/{result_id}", response_model=ExamResultResponse)
async def update_result(
    result_id: str,
    result_data: ExamResultUpdate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Update exam result"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Get existing result
        existing = db.table("exam_results").select("*, exams(id, total_marks, created_by)").eq("id", result_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Result with ID {result_id} not found", error_code="RESULT_NOT_FOUND")
        
        existing_result = existing.data
        exam_info = existing_result.get("exams", {})
        
        # For teachers, validate they can update this result
        if user_role == "teacher" and exam_info.get("created_by") != current_user["sub"]:
            raise ValidationError(
                "You can only update results for exams you created",
                error_code="UNAUTHORIZED_RESULT_UPDATE"
            )
        
        update_data = result_data.model_dump(exclude_unset=True)
        
        # Recalculate grade if marks are updated
        if "marks_obtained" in update_data:
            total_marks = update_data.get("total_marks") or existing_result.get("total_marks") or exam_info.get("total_marks", 100.0)
            percentage = (update_data["marks_obtained"] / total_marks) * 100
            active_scheme = get_active_grading_scheme(db)
            criteria = active_scheme.get("criteria") if active_scheme else None
            update_data["grade"] = calculate_grade(percentage, criteria=criteria)
        
        if not update_data:
            raise ValidationError("No data provided for update", error_code="NO_UPDATE_DATA")
        
        # Update result
        logger.info(f"Updating result {result_id}: {update_data}")
        response = db.table("exam_results").update(update_data).eq("id", result_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise DatabaseError("Failed to update result", error_code="RESULT_UPDATE_FAILED")
        
        updated_result = response.data[0]
        
        # Fetch names
        student = db.table("students").select("admission_number, user_id").eq("id", updated_result.get("student_id")).single().execute()
        if student.data:
            profile = db.table("profiles").select("full_name").eq("user_id", student.data.get("user_id")).single().execute()
            updated_result["student_name"] = profile.data.get("full_name") if profile.data else None
            updated_result["admission_number"] = student.data.get("admission_number")
        
        uploader_profile = db.table("profiles").select("full_name").eq("user_id", updated_result.get("uploaded_by")).single().execute()
        updated_result["uploaded_by_name"] = uploader_profile.data.get("full_name") if uploader_profile.data else None
        
        logger.info(f"Result updated successfully: {result_id}")
        return ExamResultResponse(**updated_result)
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update result {result_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update result: {error_message}", error_code="RESULT_UPDATE_ERROR")


@router.delete("/{result_id}")
async def delete_result(
    result_id: str,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Delete exam result"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            True,  # Admin access for deletion
            current_user.get("supabase_token")
        )
        
        # Check if result exists
        existing = db.table("exam_results").select("*, exams(created_by)").eq("id", result_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Result with ID {result_id} not found", error_code="RESULT_NOT_FOUND")
        
        existing_result = existing.data
        exam_info = existing_result.get("exams", {})
        
        # For teachers, only allow deletion of results for their exams
        if user_role == "teacher" and not is_admin:
            if exam_info.get("created_by") != current_user["sub"]:
                raise ValidationError(
                    "You can only delete results for exams you created",
                    error_code="UNAUTHORIZED_RESULT_DELETE"
                )
        
        db.table("exam_results").delete().eq("id", result_id).execute()
        
        logger.info(f"Result deleted successfully: {result_id}")
        return {"message": "Result deleted successfully"}
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete result {result_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to delete result: {error_message}", error_code="RESULT_DELETE_ERROR")







