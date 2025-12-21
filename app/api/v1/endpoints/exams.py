"""
Exams API Endpoints
Supports exam management with approval workflow
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from datetime import datetime
from app.models.exam import (
    ExamCreate, ExamUpdate, ExamResponse, ExamStatus, ExamType
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

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Create a new exam"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        exam_record = exam_data.model_dump()
        exam_record["created_by"] = current_user["sub"]
        exam_record["status"] = "draft"
        
        # Validate class exists
        class_check = db.table("classes").select("id, name, section").eq("id", exam_record["class_id"]).single().execute()
        if not class_check.data:
            raise NotFoundError(f"Class with ID {exam_record['class_id']} not found", error_code="CLASS_NOT_FOUND")
        
        # For teachers, validate they are assigned to this class
        if user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                if class_check.data.get("teacher_id") != teacher_id:
                    raise ValidationError(
                        "You can only create exams for classes you are assigned to",
                        error_code="UNAUTHORIZED_CLASS_ACCESS"
                    )
        
        # Check for duplicate exam
        duplicate_check = db.table("exams").select("id").eq("exam_name", exam_record["exam_name"])\
            .eq("class_id", exam_record["class_id"])\
            .eq("subject", exam_record["subject"])\
            .eq("term", exam_record["term"])\
            .eq("academic_year", exam_record["academic_year"])\
            .execute()
        
        if duplicate_check.data and len(duplicate_check.data) > 0:
            raise ValidationError(
                f"Exam '{exam_record['exam_name']}' already exists for this class, subject, term, and academic year",
                error_code="DUPLICATE_EXAM"
            )
        
        # Insert exam
        logger.info(f"Creating exam: {exam_record['exam_name']} for class {exam_record['class_id']}")
        response = db.table("exams").insert(exam_record).execute()
        
        if not response.data or len(response.data) == 0:
            raise DatabaseError("Failed to create exam record", error_code="EXAM_CREATE_FAILED")
        
        created_exam = response.data[0]
        
        # Fetch creator name
        profile_resp = db.table("profiles").select("full_name").eq("user_id", current_user["sub"]).single().execute()
        created_exam["created_by_name"] = profile_resp.data.get("full_name") if profile_resp.data else None
        
        logger.info(f"Exam created successfully: {created_exam.get('id')}")
        return ExamResponse(**created_exam)
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create exam: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create exam: {error_message}", error_code="EXAM_CREATE_ERROR")


@router.get("", response_model=List[ExamResponse])
async def list_exams(
    class_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List exams with optional filters"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        query = db.table("exams").select("*")
        
        # For teachers, restrict to their classes
        if user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                classes_response = db.table("classes").select("id").eq("teacher_id", teacher_id).execute()
                teacher_class_ids = [cls["id"] for cls in classes_response.data]
                
                if not teacher_class_ids:
                    return []
                
                if class_id and class_id not in teacher_class_ids:
                    return []
                
                query = query.in_("class_id", teacher_class_ids)
        
        # Apply filters
        if class_id:
            query = query.eq("class_id", class_id)
        if subject:
            query = query.ilike("subject", f"%{subject}%")
        if term:
            query = query.eq("term", term)
        if academic_year:
            query = query.eq("academic_year", academic_year)
        if exam_type:
            query = query.eq("exam_type", exam_type)
        if status:
            query = query.eq("status", status)
        
        query = query.order("created_at", desc=True)
        
        if limit > 0:
            query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        exams_data = response.data or []
        
        # Fetch creator names
        user_ids = list(set(exam.get("created_by") for exam in exams_data if exam.get("created_by")))
        profiles_map = {}
        if user_ids:
            profiles_resp = db.table("profiles").select("user_id, full_name").in_("user_id", user_ids).execute()
            profiles_map = {p.get("user_id"): p.get("full_name") for p in profiles_resp.data}
        
        for exam in exams_data:
            exam["created_by_name"] = profiles_map.get(exam.get("created_by"))
        
        return [ExamResponse(**exam) for exam in exams_data]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch exams: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch exams: {error_message}", error_code="EXAM_FETCH_ERROR")


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(
    exam_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get exam by ID"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        response = db.table("exams").select("*").eq("id", exam_id).single().execute()
        
        if not response.data:
            raise NotFoundError(f"Exam with ID {exam_id} not found", error_code="EXAM_NOT_FOUND")
        
        exam = response.data
        
        # For teachers, verify they can access this exam
        if user_role == "teacher":
            teacher_check = supabase_admin.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                teacher_id = teacher_check.data["id"]
                class_check = db.table("classes").select("teacher_id").eq("id", exam.get("class_id")).single().execute()
                if not class_check.data or class_check.data.get("teacher_id") != teacher_id:
                    raise NotFoundError("Exam not found", error_code="EXAM_NOT_FOUND")
        
        # Fetch creator name
        profile_resp = db.table("profiles").select("full_name").eq("user_id", exam.get("created_by")).single().execute()
        exam["created_by_name"] = profile_resp.data.get("full_name") if profile_resp.data else None
        
        return ExamResponse(**exam)
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch exam {exam_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch exam: {error_message}", error_code="EXAM_FETCH_ERROR")


@router.put("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: str,
    exam_data: ExamUpdate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Update exam"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Get existing exam
        existing = db.table("exams").select("*").eq("id", exam_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Exam with ID {exam_id} not found", error_code="EXAM_NOT_FOUND")
        
        existing_exam = existing.data
        
        # For teachers, validate they can update this exam
        if user_role == "teacher":
            if existing_exam.get("created_by") != current_user["sub"] or existing_exam.get("status") != "draft":
                raise ValidationError(
                    "You can only update draft exams you created",
                    error_code="UNAUTHORIZED_EXAM_UPDATE"
                )
        
        update_data = exam_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise ValidationError("No data provided for update", error_code="NO_UPDATE_DATA")
        
        # Update exam
        logger.info(f"Updating exam {exam_id}: {update_data}")
        response = db.table("exams").update(update_data).eq("id", exam_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise DatabaseError("Failed to update exam", error_code="EXAM_UPDATE_FAILED")
        
        updated_exam = response.data[0]
        
        # Fetch creator name
        profile_resp = db.table("profiles").select("full_name").eq("user_id", updated_exam.get("created_by")).single().execute()
        updated_exam["created_by_name"] = profile_resp.data.get("full_name") if profile_resp.data else None
        
        logger.info(f"Exam updated successfully: {exam_id}")
        return ExamResponse(**updated_exam)
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update exam {exam_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update exam: {error_message}", error_code="EXAM_UPDATE_ERROR")


@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: str,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Delete exam"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            True,  # Admin access for deletion
            current_user.get("supabase_token")
        )
        
        # Check if exam exists
        existing = db.table("exams").select("id, created_by, status").eq("id", exam_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Exam with ID {exam_id} not found", error_code="EXAM_NOT_FOUND")
        
        existing_exam = existing.data
        
        # For teachers, only allow deletion of draft exams they created
        if user_role == "teacher" and not is_admin:
            if existing_exam.get("created_by") != current_user["sub"] or existing_exam.get("status") != "draft":
                raise ValidationError(
                    "You can only delete draft exams you created",
                    error_code="UNAUTHORIZED_EXAM_DELETE"
                )
        
        db.table("exams").delete().eq("id", exam_id).execute()
        
        logger.info(f"Exam deleted successfully: {exam_id}")
        return {"message": "Exam deleted successfully"}
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete exam {exam_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to delete exam: {error_message}", error_code="EXAM_DELETE_ERROR")


@router.get("/pending-approval/list")
async def get_pending_approvals(
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Get papers/exams pending approval (for principal/admin)"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            True,  # Admin access
            current_user.get("supabase_token")
        )
        
        # Get papers pending approval
        response = db.table("papers")\
            .select("*")\
            .eq("approval_status", "pending")\
            .order("submitted_for_approval_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        pending_papers_data = response.data or []
        
        # Fetch uploaded_by names from profiles
        user_ids = list(set(p.get("uploaded_by") for p in pending_papers_data if p.get("uploaded_by")))
        profiles_map = {}
        if user_ids:
            profiles_resp = supabase_admin.table("profiles").select("user_id, full_name").in_("user_id", user_ids).execute()
            profiles_map = {p.get("user_id"): p.get("full_name") for p in profiles_resp.data}
        
        # Fetch exam details if exam_id exists
        exam_ids = list(set(p.get("exam_id") for p in pending_papers_data if p.get("exam_id")))
        exams_map = {}
        if exam_ids:
            exams_resp = db.table("exams").select("id, exam_name, subject").in_("id", exam_ids).execute()
            exams_map = {e.get("id"): {"exam_name": e.get("exam_name"), "subject": e.get("subject")} for e in exams_resp.data}
        
        # Map data to response
        pending_papers = []
        for paper in pending_papers_data:
            paper_dict = dict(paper)
            paper_dict["uploaded_by_name"] = profiles_map.get(paper.get("uploaded_by"))
            if paper.get("exam_id") and paper.get("exam_id") in exams_map:
                exam_info = exams_map[paper.get("exam_id")]
                paper_dict["exams"] = {
                    "id": paper.get("exam_id"),
                    "exam_name": exam_info.get("exam_name"),
                    "subject": exam_info.get("subject")
                }
            pending_papers.append(paper_dict)
        
        logger.info(f"Retrieved {len(pending_papers)} papers pending approval")
        return {"papers": pending_papers, "count": len(pending_papers)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch pending approvals: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch pending approvals: {error_message}", error_code="PENDING_APPROVALS_ERROR")

