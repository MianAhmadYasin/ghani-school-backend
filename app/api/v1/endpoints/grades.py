from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.grade import GradeCreate, GradeUpdate, GradeResponse, BulkGradeCreate
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
from app.core.grading_utils import calculate_grade, get_active_grading_scheme

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=GradeResponse, status_code=status.HTTP_201_CREATED)
async def create_grade(
    grade_data: GradeCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Create a new grade record with automatic grade calculation and validation"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Auto-calculate grade if not provided
        grade_record = grade_data.model_dump()
        # Term normalization happens in the model validator (Final → Annual)
        if not grade_record.get("grade"):
            # Get active grading scheme from database
            active_scheme = get_active_grading_scheme(db)
            criteria = active_scheme.get("criteria") if active_scheme else None
            grade_record["grade"] = calculate_grade(grade_record["marks"], criteria=criteria)
            logger.debug(f"Auto-calculated grade {grade_record['grade']} for marks {grade_record['marks']} using {'custom scheme' if criteria else 'default system'}")
        
        # Log term normalization if it occurred
        if grade_data.term == "Final" and grade_record.get("term") == "Annual":
            logger.debug(f"Normalized term from 'Final' to 'Annual' for grade creation")
        
        # Validate student exists and belongs to the specified class
        student_check = db.table("students").select("id, class_id").eq("id", grade_record["student_id"]).single().execute()
        if not student_check.data:
            raise NotFoundError(f"Student with ID {grade_record['student_id']} not found", error_code="STUDENT_NOT_FOUND")
        
        student = student_check.data
        if student.get("class_id") != grade_record["class_id"]:
            raise ValidationError(
                f"Student {grade_record['student_id']} does not belong to class {grade_record['class_id']}",
                error_code="STUDENT_CLASS_MISMATCH"
            )
        
        # For teachers, validate they are assigned to this class
        if user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                class_check = db.table("classes").select("teacher_id").eq("id", grade_record["class_id"]).single().execute()
                if class_check.data and class_check.data.get("teacher_id") != teacher_id:
                    logger.warning(f"Teacher {teacher_id} attempted to create grade for unauthorized class {grade_record['class_id']}")
                    raise ValidationError(
                        "You can only create grades for classes you are assigned to",
                        error_code="UNAUTHORIZED_CLASS_ACCESS"
                    )
        
        # Check for duplicate grade (same student, subject, term, academic_year)
        # Note: term is already normalized to "Annual" if it was "Final"
        duplicate_check = db.table("grades").select("id").eq("student_id", grade_record["student_id"])\
            .eq("subject", grade_record["subject"])\
            .eq("term", grade_record["term"])\
            .eq("academic_year", grade_record["academic_year"])\
            .execute()
        
        if duplicate_check.data and len(duplicate_check.data) > 0:
            logger.warning(f"Duplicate grade attempt: student={grade_record['student_id']}, subject={grade_record['subject']}, term={grade_record['term']}, year={grade_record['academic_year']}")
            raise ConflictError(
                f"Grade already exists for student {grade_record['student_id']}, subject {grade_record['subject']}, "
                f"term {grade_record['term']}, year {grade_record['academic_year']}",
                error_code="DUPLICATE_GRADE"
            )
        
        # Insert grade
        logger.info(f"Creating grade: student={grade_record['student_id']}, subject={grade_record['subject']}, marks={grade_record['marks']}, grade={grade_record['grade']}")
        response = db.table("grades").insert(grade_record).execute()
        
        if not response.data or len(response.data) == 0:
            raise DatabaseError("Failed to create grade record", error_code="GRADE_CREATE_FAILED")
        
        created_grade = response.data[0]
        logger.info(f"Grade created successfully: {created_grade.get('id')}")
        return GradeResponse(**created_grade)
        
    except (NotFoundError, ValidationError, ConflictError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create grade: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create grade: {error_message}", error_code="GRADE_CREATE_ERROR")


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def create_bulk_grades(
    bulk_data: BulkGradeCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Create multiple grade records at once with validation"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Prepare grades with auto-calculation
        grades_to_insert = []
        errors = []
        
        for idx, grade in enumerate(bulk_data.grades):
            try:
                grade_dict = grade.model_dump()
                
                # Normalize term if needed (Final -> Annual)
                if grade_dict.get("term") == "Final":
                    grade_dict["term"] = "Annual"
                
                # Auto-calculate grade if not provided
                if not grade_dict.get("grade"):
                    # Get active grading scheme from database
                    active_scheme = get_active_grading_scheme(db)
                    criteria = active_scheme.get("criteria") if active_scheme else None
                    grade_dict["grade"] = calculate_grade(grade_dict["marks"], criteria=criteria)
                    logger.debug(f"Auto-calculated grade {grade_dict['grade']} for marks {grade_dict['marks']}")
                
                # Validate student exists and belongs to class
                student_check = db.table("students").select("id, class_id").eq("id", grade_dict["student_id"]).single().execute()
                if not student_check.data:
                    errors.append(f"Grade {idx + 1}: Student {grade_dict['student_id']} not found")
                    continue
                
                student = student_check.data
                if student.get("class_id") != grade_dict["class_id"]:
                    errors.append(f"Grade {idx + 1}: Student does not belong to class {grade_dict['class_id']}")
                    continue
                
                # Check for duplicates (term is already normalized to "Annual" if it was "Final")
                duplicate_check = db.table("grades").select("id").eq("student_id", grade_dict["student_id"])\
                    .eq("subject", grade_dict["subject"])\
                    .eq("term", grade_dict["term"])\
                    .eq("academic_year", grade_dict["academic_year"])\
                    .execute()
                
                if duplicate_check.data and len(duplicate_check.data) > 0:
                    errors.append(f"Grade {idx + 1}: Duplicate grade already exists")
                    continue
                
                grades_to_insert.append(grade_dict)
                
            except Exception as e:
                errors.append(f"Grade {idx + 1}: {str(e)}")
                continue
        
        if not grades_to_insert:
            raise ValidationError(
                f"No valid grades to insert. Errors: {'; '.join(errors)}",
                error_code="NO_VALID_GRADES"
            )
        
        # Insert all valid grades
        logger.info(f"Bulk creating {len(grades_to_insert)} grades")
        response = db.table("grades").insert(grades_to_insert).execute()
        
        created_grades = response.data or []
        result = {
            "message": f"Created {len(created_grades)} grade records",
            "grades": created_grades,
            "success_count": len(created_grades),
            "total_count": len(bulk_data.grades),
            "errors": errors if errors else None
        }
        
        logger.info(f"Bulk grade creation completed: {result['success_count']}/{result['total_count']} successful")
        return result
        
    except (ValidationError, NotFoundError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create bulk grades: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create bulk grades: {error_message}", error_code="BULK_GRADE_CREATE_ERROR")


@router.get("", response_model=list[GradeResponse])
async def list_grades(
    student_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List grades with optional filters and proper RLS enforcement"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        query = db.table("grades").select("*")
        
        # For teachers, restrict to their classes only
        if user_role == "teacher":
            # Get teacher's class IDs
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                classes_response = db.table("classes").select("id").eq("teacher_id", teacher_id).execute()
                teacher_class_ids = [cls["id"] for cls in classes_response.data]
                
                if not teacher_class_ids:
                    # Teacher has no classes assigned
                    return []
                
                # Filter by teacher's classes
                if class_id and class_id not in teacher_class_ids:
                    # Requested class is not assigned to this teacher
                    return []
                
                query = query.in_("class_id", teacher_class_ids)
        
        # For students, restrict to their own grades only
        elif user_role == "student":
            # Get student ID
            student_check = db.table("students").select("id").eq("user_id", current_user["sub"]).single().execute()
            if student_check.data:
                student_id_from_user = student_check.data["id"]
                
                if student_id and student_id != student_id_from_user:
                    # Requesting another student's grades - not allowed
                    return []
                
                query = query.eq("student_id", student_id_from_user)
            else:
                # Student record not found
                return []
        
        # Apply filters
        if student_id:
            query = query.eq("student_id", student_id)
        
        if class_id:
            query = query.eq("class_id", class_id)
        
        if subject:
            query = query.eq("subject", subject)
        
        if term:
            # Normalize term for query (Final -> Annual)
            normalized_term = "Annual" if term == "Final" else term
            query = query.eq("term", normalized_term)
        
        if academic_year:
            query = query.eq("academic_year", academic_year)
        
        # Apply ordering and pagination
        query = query.order("created_at", desc=True)
        
        # Apply pagination
        if limit > 0:
            query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        
        # Normalize 'Annual' back to 'Final' for display if needed
        # But keep 'Annual' in database for consistency
        grades_data = response.data or []
        
        logger.debug(f"Retrieved {len(grades_data)} grades for user {current_user.get('sub')} (role: {user_role})")
        
        # Return empty list if no grades found (don't raise error)
        if not grades_data:
            return []
        
        return [GradeResponse(**grade) for grade in grades_data]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch grades: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch grades: {error_message}", error_code="GRADE_FETCH_ERROR")


@router.get("/me", response_model=list[GradeResponse])
async def get_my_grades(
    term: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    current_user: dict = Depends(require_role(["student"]))
):
    """Get current student's grades with proper RLS enforcement"""
    try:
        user_id = current_user["sub"]
        # Students should use RLS-enabled client, not admin client
        db = get_request_scoped_client(
            current_user.get("access_token"),
            False,  # Not admin
            current_user.get("supabase_token")
        )
        
        # Get student ID - use RLS-enabled query
        student_response = db.table("students").select("id").eq("user_id", user_id).single().execute()
        
        if not student_response.data:
            raise NotFoundError("Student record not found for current user", error_code="STUDENT_NOT_FOUND")
        
        student_id = student_response.data["id"]
        
        # Get grades - RLS will automatically filter to this student's grades
        query = db.table("grades").select("*").eq("student_id", student_id)
        
        if term:
            query = query.eq("term", term)
        
        if academic_year:
            query = query.eq("academic_year", academic_year)
        
        query = query.order("created_at", desc=True)
        response = query.execute()
        
        grades_data = response.data or []
        logger.debug(f"Retrieved {len(grades_data)} grades for student {student_id}")
        
        if not grades_data:
            return []
        
        return [GradeResponse(**grade) for grade in grades_data]
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch student grades: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch grades: {error_message}", error_code="GRADE_FETCH_ERROR")


@router.get("/{grade_id}", response_model=GradeResponse)
async def get_grade(
    grade_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get grade by ID with proper RLS enforcement"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        response = db.table("grades").select("*").eq("id", grade_id).single().execute()
        
        if not response.data:
            raise NotFoundError(f"Grade with ID {grade_id} not found", error_code="GRADE_NOT_FOUND")
        
        grade = response.data  # single() returns dict directly, not list
        
        # For students, verify they can access this grade
        if user_role == "student":
            student_check = db.table("students").select("id").eq("user_id", current_user["sub"]).single().execute()
            if student_check.data:
                student_id = student_check.data["id"]
                if grade.get("student_id") != student_id:
                    raise NotFoundError("Grade not found", error_code="GRADE_NOT_FOUND")
        
        # For teachers, verify they can access this grade (their class)
        elif user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                class_check = db.table("classes").select("teacher_id").eq("id", grade.get("class_id")).single().execute()
                if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                    raise NotFoundError("Grade not found", error_code="GRADE_NOT_FOUND")
        
        return GradeResponse(**grade)
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch grade {grade_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch grade: {error_message}", error_code="GRADE_FETCH_ERROR")


@router.put("/{grade_id}", response_model=GradeResponse)
async def update_grade(
    grade_id: str,
    grade_data: GradeUpdate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Update grade record with automatic grade recalculation"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Get existing grade
        existing = db.table("grades").select("*").eq("id", grade_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Grade with ID {grade_id} not found", error_code="GRADE_NOT_FOUND")
        
        existing_grade = existing.data  # single() returns dict directly, not list
        
        # For teachers, validate they can update this grade
        if user_role == "teacher":
            class_id = existing_grade.get("class_id")
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                class_check = db.table("classes").select("teacher_id").eq("id", class_id).single().execute()
                if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                    logger.warning(f"Teacher {teacher_id} attempted to update grade {grade_id} for unauthorized class {class_id}")
                    raise ValidationError(
                        "You can only update grades for classes you are assigned to",
                        error_code="UNAUTHORIZED_CLASS_ACCESS"
                    )
        
        update_data = grade_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise ValidationError("No data provided for update", error_code="NO_UPDATE_DATA")
        
        # Recalculate grade if marks are updated
        if "marks" in update_data:
            # Get active grading scheme from database
            active_scheme = get_active_grading_scheme(db)
            criteria = active_scheme.get("criteria") if active_scheme else None
            update_data["grade"] = calculate_grade(update_data["marks"], criteria=criteria)
            logger.debug(f"Recalculated grade {update_data['grade']} for marks {update_data['marks']}")
        
        # Update grade
        logger.info(f"Updating grade {grade_id}: {update_data}")
        response = db.table("grades").update(update_data).eq("id", grade_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise DatabaseError("Failed to update grade", error_code="GRADE_UPDATE_FAILED")
        
        updated_grade = response.data[0]
        logger.info(f"Grade updated successfully: {grade_id}")
        return GradeResponse(**updated_grade)
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update grade {grade_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update grade: {error_message}", error_code="GRADE_UPDATE_ERROR")


@router.delete("/{grade_id}")
async def delete_grade(
    grade_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete grade record"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            True,  # Admin/Principal can delete
            current_user.get("supabase_token")
        )
        
        # Check if grade exists
        existing = db.table("grades").select("id").eq("id", grade_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Grade with ID {grade_id} not found", error_code="GRADE_NOT_FOUND")
        
        db.table("grades").delete().eq("id", grade_id).execute()
        
        logger.info(f"Grade deleted successfully: {grade_id}")
        return {"message": "Grade deleted successfully"}
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete grade {grade_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to delete grade: {error_message}", error_code="GRADE_DELETE_ERROR")


@router.get("/positions")
async def get_positions(
    class_id: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    top_n: int = Query(3, ge=1, le=10),
    current_user: dict = Depends(get_current_user)
):
    """Get top N student positions for a class and term"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Normalize term (Final -> Annual)
        normalized_term = "Annual" if term == "Final" else term if term else None
        
        # Validate required parameters
        if not class_id or not normalized_term or not academic_year:
            raise ValidationError(
                "class_id, term, and academic_year are required",
                error_code="MISSING_PARAMETERS"
            )
        
        # For teachers, validate they are assigned to this class
        if user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                class_check = db.table("classes").select("teacher_id").eq("id", class_id).single().execute()
                if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                    raise ValidationError(
                        "You can only view positions for classes you are assigned to",
                        error_code="UNAUTHORIZED_CLASS_ACCESS"
                    )
        
        # Get class info
        class_info = db.table("classes").select("name, section").eq("id", class_id).single().execute()
        if not class_info.data:
            raise NotFoundError(f"Class with ID {class_id} not found", error_code="CLASS_NOT_FOUND")
        
        class_name = f"{class_info.data['name']} - {class_info.data['section']}"
        
        # Get all grades for this class, term, and year
        grades_response = db.table("grades").select("student_id, marks").eq("class_id", class_id).eq("term", normalized_term).eq("academic_year", academic_year).execute()
        
        if not grades_response.data:
            return {
                "class_id": class_id,
                "class_name": class_name,
                "term": term if term else normalized_term,
                "academic_year": academic_year,
                "positions": [],
                "class_average": 0
            }
        
        # Get unique student IDs
        student_ids = list(set(grade["student_id"] for grade in grades_response.data))
        
        # Fetch all student info with profiles in one batch
        student_info_map: dict[str, dict] = {}
        if student_ids:
            students_resp = db.table("students").select("id, admission_number, user_id").in_("id", student_ids).execute()
            user_ids = [s.get("user_id") for s in students_resp.data if s.get("user_id")]
            
            # Fetch all profiles in one batch
            profiles_map = {}
            if user_ids:
                profiles_resp = db.table("profiles").select("user_id, full_name").in_("user_id", user_ids).execute()
                profiles_map = {p.get("user_id"): p.get("full_name", "Unknown") for p in profiles_resp.data}
            
            # Build student info map
            for student in students_resp.data:
                student_id = student.get("id")
                user_id = student.get("user_id")
                student_info_map[student_id] = {
                    "admission_number": student.get("admission_number", ""),
                    "full_name": profiles_map.get(user_id, "Unknown") if user_id else "Unknown"
                }
        
        # Calculate average marks per student
        student_stats: dict[str, dict] = {}
        
        for grade in grades_response.data:
            student_id = grade["student_id"]
            marks = float(grade["marks"])
            
            if student_id not in student_stats:
                student_info = student_info_map.get(student_id, {})
                
                student_stats[student_id] = {
                    "student_id": student_id,
                    "student_name": student_info.get("full_name", "Unknown"),
                    "admission_number": student_info.get("admission_number", ""),
                    "total_marks": 0,
                    "total_subjects": 0,
                    "passed_subjects": 0
                }
            
            student_stats[student_id]["total_marks"] += marks
            student_stats[student_id]["total_subjects"] += 1
            
            # Check if passing (assuming 50% is passing threshold, can be enhanced with grading scheme)
            if marks >= 50:
                student_stats[student_id]["passed_subjects"] += 1
        
        # Calculate averages and create position list
        position_list = []
        for student_id, stats in student_stats.items():
            if stats["total_subjects"] > 0:
                average_marks = stats["total_marks"] / stats["total_subjects"]
                position_list.append({
                    "student_id": stats["student_id"],
                    "student_name": stats["student_name"],
                    "admission_number": stats["admission_number"],
                    "average_marks": round(average_marks, 2),
                    "total_marks": stats["total_marks"],
                    "total_subjects": stats["total_subjects"],
                    "passed_subjects": stats["passed_subjects"]
                })
        
        # Sort by average marks descending
        position_list.sort(key=lambda x: x["average_marks"], reverse=True)
        
        # Assign positions (handle ties - same position, skip next)
        current_position = 1
        for idx, student in enumerate(position_list):
            if idx > 0 and position_list[idx - 1]["average_marks"] != student["average_marks"]:
                current_position = idx + 1
            student["position"] = current_position
        
        # Get top N positions
        top_positions = position_list[:top_n]
        
        # Calculate class average
        if position_list:
            class_average = sum(s["average_marks"] for s in position_list) / len(position_list)
        else:
            class_average = 0
        
        result = {
            "class_id": class_id,
            "class_name": class_name,
            "term": term if term else normalized_term,
            "academic_year": academic_year,
            "positions": top_positions,
            "class_average": round(class_average, 2)
        }
        
        logger.info(f"Retrieved positions for class {class_id}, term {normalized_term}: {len(top_positions)} positions")
        return result
        
    except (ValidationError, NotFoundError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to fetch positions: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch positions: {error_message}", error_code="POSITIONS_FETCH_ERROR")



