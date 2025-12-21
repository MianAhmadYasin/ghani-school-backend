from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from app.models.grading_scheme import (
    GradingSchemeCreate, GradingSchemeUpdate, GradingSchemeResponse,
    GradingCriterionCreate, GradingCriterionUpdate, GradingCriterionResponse,
    BulkGradingSchemeUpdate
)
from app.core.supabase import supabase_admin, get_request_scoped_client
from app.core.security import require_role, get_current_user
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


@router.post("", response_model=GradingSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_grading_scheme(
    scheme_data: GradingSchemeCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new grading scheme with criteria"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # If this is set as default, unset other defaults
        if scheme_data.is_default:
            db.table("grading_schemes").update({"is_default": False}).neq("id", "00000000-0000-0000-0000-000000000000").execute()
        
        # Create scheme
        scheme_dict = {
            "name": scheme_data.name,
            "description": scheme_data.description,
            "is_active": scheme_data.is_active,
            "is_default": scheme_data.is_default,
            "created_by": current_user.get("sub"),
            "updated_by": current_user.get("sub")
        }
        
        scheme_response = db.table("grading_schemes").insert(scheme_dict).execute()
        
        if not scheme_response.data or len(scheme_response.data) == 0:
            raise DatabaseError("Failed to create grading scheme", error_code="SCHEME_CREATE_FAILED")
        
        scheme_id = scheme_response.data[0]["id"]
        
        # Create criteria
        criteria_to_insert = []
        for criterion in scheme_data.criteria:
            criteria_dict = {
                "grading_scheme_id": scheme_id,
                "grade_name": criterion.grade_name,
                "min_marks": criterion.min_marks,
                "max_marks": criterion.max_marks,
                "gpa_value": criterion.gpa_value,
                "is_passing": criterion.is_passing,
                "display_order": criterion.display_order
            }
            criteria_to_insert.append(criteria_dict)
        
        if criteria_to_insert:
            criteria_response = db.table("grading_criteria").insert(criteria_to_insert).execute()
            logger.info(f"Created grading scheme '{scheme_data.name}' with {len(criteria_to_insert)} criteria")
        else:
            # Delete scheme if no criteria
            db.table("grading_schemes").delete().eq("id", scheme_id).execute()
            raise ValidationError("At least one grading criterion is required", error_code="NO_CRITERIA")
        
        # Fetch complete scheme with criteria
        scheme = db.table("grading_schemes").select("*").eq("id", scheme_id).single().execute()
        criteria = db.table("grading_criteria").select("*").eq("grading_scheme_id", scheme_id).order("display_order").execute()
        
        scheme_data = scheme.data
        scheme_data["criteria"] = criteria.data or []
        
        return GradingSchemeResponse(**scheme_data)
        
    except (ValidationError, ConflictError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create grading scheme: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create grading scheme: {error_message}", error_code="SCHEME_CREATE_ERROR")


@router.get("", response_model=List[GradingSchemeResponse])
async def list_grading_schemes(
    is_active: Optional[bool] = Query(None),
    include_default: bool = Query(True),
    current_user: dict = Depends(get_current_user)
):
    """List all grading schemes"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        query = db.table("grading_schemes").select("*")
        
        if is_active is not None:
            query = query.eq("is_active", is_active)
        
        if include_default:
            query = query.order("is_default", desc=True)
        
        query = query.order("created_at", desc=True)
        response = query.execute()
        
        schemes_data = response.data or []
        
        # Fetch criteria for each scheme
        result = []
        for scheme in schemes_data:
            criteria_response = db.table("grading_criteria").select("*").eq("grading_scheme_id", scheme["id"]).order("display_order").execute()
            scheme["criteria"] = criteria_response.data or []
            result.append(GradingSchemeResponse(**scheme))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch grading schemes: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch grading schemes: {error_message}", error_code="SCHEME_FETCH_ERROR")


@router.get("/default", response_model=GradingSchemeResponse)
async def get_default_grading_scheme(
    current_user: dict = Depends(get_current_user)
):
    """Get the default/active grading scheme"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Try to get default scheme first
        default_response = db.table("grading_schemes").select("*").eq("is_default", True).eq("is_active", True).single().execute()
        
        if not default_response.data:
            # If no default, get first active scheme
            active_response = db.table("grading_schemes").select("*").eq("is_active", True).order("created_at").limit(1).single().execute()
            if not active_response.data:
                raise NotFoundError("No active grading scheme found", error_code="NO_ACTIVE_SCHEME")
            scheme = active_response.data
        else:
            scheme = default_response.data
        
        # Fetch criteria
        criteria_response = db.table("grading_criteria").select("*").eq("grading_scheme_id", scheme["id"]).order("display_order").execute()
        scheme["criteria"] = criteria_response.data or []
        
        return GradingSchemeResponse(**scheme)
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch default grading scheme: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch default grading scheme: {error_message}", error_code="SCHEME_FETCH_ERROR")


@router.get("/{scheme_id}", response_model=GradingSchemeResponse)
async def get_grading_scheme(
    scheme_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific grading scheme by ID"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        scheme_response = db.table("grading_schemes").select("*").eq("id", scheme_id).single().execute()
        
        if not scheme_response.data:
            raise NotFoundError(f"Grading scheme with ID {scheme_id} not found", error_code="SCHEME_NOT_FOUND")
        
        scheme = scheme_response.data
        
        # Fetch criteria
        criteria_response = db.table("grading_criteria").select("*").eq("grading_scheme_id", scheme_id).order("display_order").execute()
        scheme["criteria"] = criteria_response.data or []
        
        return GradingSchemeResponse(**scheme)
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch grading scheme: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch grading scheme: {error_message}", error_code="SCHEME_FETCH_ERROR")


@router.put("/{scheme_id}", response_model=GradingSchemeResponse)
async def update_grading_scheme(
    scheme_id: str,
    scheme_data: GradingSchemeUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update a grading scheme"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if scheme exists
        existing = db.table("grading_schemes").select("*").eq("id", scheme_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Grading scheme with ID {scheme_id} not found", error_code="SCHEME_NOT_FOUND")
        
        # If setting as default, unset other defaults
        if scheme_data.is_default:
            db.table("grading_schemes").update({"is_default": False}).neq("id", scheme_id).execute()
        
        # Update scheme
        update_dict = scheme_data.model_dump(exclude_unset=True)
        update_dict["updated_by"] = current_user.get("sub")
        
        if not update_dict:
            raise ValidationError("No data provided for update", error_code="NO_UPDATE_DATA")
        
        response = db.table("grading_schemes").update(update_dict).eq("id", scheme_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise DatabaseError("Failed to update grading scheme", error_code="SCHEME_UPDATE_FAILED")
        
        # Fetch updated scheme with criteria
        scheme = response.data[0]
        criteria_response = db.table("grading_criteria").select("*").eq("grading_scheme_id", scheme_id).order("display_order").execute()
        scheme["criteria"] = criteria_response.data or []
        
        logger.info(f"Updated grading scheme {scheme_id}")
        return GradingSchemeResponse(**scheme)
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update grading scheme: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update grading scheme: {error_message}", error_code="SCHEME_UPDATE_ERROR")


@router.put("/{scheme_id}/criteria", response_model=GradingSchemeResponse)
async def update_grading_scheme_criteria(
    scheme_id: str,
    bulk_data: BulkGradingSchemeUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update all criteria for a grading scheme"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Verify scheme exists
        scheme_check = db.table("grading_schemes").select("id").eq("id", scheme_id).single().execute()
        if not scheme_check.data:
            raise NotFoundError(f"Grading scheme with ID {scheme_id} not found", error_code="SCHEME_NOT_FOUND")
        
        # Delete existing criteria
        db.table("grading_criteria").delete().eq("grading_scheme_id", scheme_id).execute()
        
        # Insert new criteria
        criteria_to_insert = []
        for criterion in bulk_data.criteria:
            criteria_dict = {
                "grading_scheme_id": scheme_id,
                "grade_name": criterion.grade_name,
                "min_marks": criterion.min_marks,
                "max_marks": criterion.max_marks,
                "gpa_value": criterion.gpa_value,
                "is_passing": criterion.is_passing,
                "display_order": criterion.display_order
            }
            criteria_to_insert.append(criteria_dict)
        
        if not criteria_to_insert:
            raise ValidationError("At least one grading criterion is required", error_code="NO_CRITERIA")
        
        db.table("grading_criteria").insert(criteria_to_insert).execute()
        
        # Update scheme updated_by
        db.table("grading_schemes").update({"updated_by": current_user.get("sub")}).eq("id", scheme_id).execute()
        
        # Fetch updated scheme with criteria
        scheme_response = db.table("grading_schemes").select("*").eq("id", scheme_id).single().execute()
        criteria_response = db.table("grading_criteria").select("*").eq("grading_scheme_id", scheme_id).order("display_order").execute()
        
        scheme = scheme_response.data
        scheme["criteria"] = criteria_response.data or []
        
        logger.info(f"Updated criteria for grading scheme {scheme_id}")
        return GradingSchemeResponse(**scheme)
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update grading scheme criteria: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update grading scheme criteria: {error_message}", error_code="CRITERIA_UPDATE_ERROR")


@router.delete("/{scheme_id}")
async def delete_grading_scheme(
    scheme_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete a grading scheme"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if scheme exists
        existing = db.table("grading_schemes").select("id, is_default").eq("id", scheme_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Grading scheme with ID {scheme_id} not found", error_code="SCHEME_NOT_FOUND")
        
        # Prevent deletion of default scheme
        if existing.data.get("is_default"):
            raise ValidationError("Cannot delete the default grading scheme. Set another scheme as default first.", error_code="CANNOT_DELETE_DEFAULT")
        
        # Delete criteria first (CASCADE should handle this, but explicit is better)
        db.table("grading_criteria").delete().eq("grading_scheme_id", scheme_id).execute()
        
        # Delete scheme
        db.table("grading_schemes").delete().eq("id", scheme_id).execute()
        
        logger.info(f"Deleted grading scheme {scheme_id}")
        return {"message": "Grading scheme deleted successfully"}
        
    except (NotFoundError, ValidationError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete grading scheme: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to delete grading scheme: {error_message}", error_code="SCHEME_DELETE_ERROR")








