"""
Exam Settings API Endpoints
School-specific exam configuration
"""

from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime
from app.models.exam import ExamSettingsResponse, ExamSettingsUpdate
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


@router.get("", response_model=ExamSettingsResponse)
async def get_exam_settings(
    current_user: dict = Depends(get_current_user)
):
    """Get school exam settings"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"],
            current_user.get("supabase_token")
        )
        
        response = db.table("exam_settings").select("*").limit(1).execute()
        
        if not response.data or len(response.data) == 0:
            # Return default settings if none exist
            return ExamSettingsResponse(
                id="default",
                school_name="Default School",
                terms_config=["First Term", "Second Term", "Third Term", "Final"],
                exam_types=["term_exam", "mid_term", "final", "quiz", "assignment", "annual"],
                bulk_upload_enabled=True,
                approval_required=True,
                auto_calculate_grade=True,
                created_at=datetime.utcnow(),
                created_by=None,
                updated_by=None
            )
        
        settings = response.data[0]
        return ExamSettingsResponse(**settings)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch exam settings: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch exam settings: {error_message}", error_code="SETTINGS_FETCH_ERROR")


@router.put("", response_model=ExamSettingsResponse)
async def update_exam_settings(
    settings_data: ExamSettingsUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update school exam settings"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            True,  # Admin access
            current_user.get("supabase_token")
        )
        
        # Check if settings exist
        existing = db.table("exam_settings").select("*").limit(1).execute()
        
        update_data = settings_data.model_dump(exclude_unset=True)
        update_data["updated_by"] = current_user["sub"]
        
        if existing.data and len(existing.data) > 0:
            # Update existing
            response = db.table("exam_settings").update(update_data).eq("id", existing.data[0]["id"]).execute()
        else:
            # Create new
            update_data["created_by"] = current_user["sub"]
            response = db.table("exam_settings").insert(update_data).execute()
        
        if not response.data or len(response.data) == 0:
            raise DatabaseError("Failed to update exam settings", error_code="SETTINGS_UPDATE_FAILED")
        
        updated_settings = response.data[0]
        logger.info(f"Exam settings updated successfully")
        return ExamSettingsResponse(**updated_settings)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update exam settings: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update exam settings: {error_message}", error_code="SETTINGS_UPDATE_ERROR")

