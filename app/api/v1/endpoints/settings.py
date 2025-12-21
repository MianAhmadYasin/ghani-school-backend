from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, Literal
from app.models.settings import (
    SystemSettingCreate, SystemSettingUpdate, SystemSettingResponse,
    RolePermissionCreate, RolePermissionUpdate, RolePermissionResponse,
    FeeStructureCreate, FeeStructureUpdate, FeeStructureResponse,
    AcademicYearCreate, AcademicYearUpdate, AcademicYearResponse,
    BulkSettingsUpdate, SettingsExport
)
from app.core.supabase import supabase, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ==================== System Settings ====================

@router.get("/system", response_model=list[SystemSettingResponse])
async def get_system_settings(
    category: Optional[Literal['general', 'academic', 'financial', 'security', 'notification', 'appearance']] = Query(None),
    public_only: bool = Query(False),
    current_user: dict = Depends(get_current_user)
):
    """Get system settings"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        query = db.table("system_settings").select("*")
        
        if category:
            query = query.eq("category", category)
        if public_only or current_user.get("role") not in ["admin", "principal"]:
            query = query.eq("is_public", True)
        
        response = query.execute()
        return [SystemSettingResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/system/{setting_key}", response_model=SystemSettingResponse)
async def get_system_setting(
    setting_key: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific system setting"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        response = db.table("system_settings").select("*").eq("setting_key", setting_key).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
        
        setting = response.data[0]
        if not setting.get("is_public") and current_user.get("role") not in ["admin", "principal"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        return SystemSettingResponse(**setting)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/system", response_model=SystemSettingResponse, status_code=status.HTTP_201_CREATED)
async def create_system_setting(
    setting_data: SystemSettingCreate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Create a new system setting"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        setting_record = setting_data.model_dump()
        setting_record["updated_by"] = current_user["sub"]
        
        response = db.table("system_settings").insert(setting_record).execute()
        return SystemSettingResponse(**response.data[0])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/system/{setting_key}", response_model=SystemSettingResponse)
async def update_system_setting(
    setting_key: str,
    setting_data: SystemSettingUpdate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Update a system setting"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if setting exists
        existing = db.table("system_settings").select("*").eq("setting_key", setting_key).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
        
        # Update only provided fields
        update_data = {k: v for k, v in setting_data.model_dump().items() if v is not None}
        update_data["updated_by"] = current_user["sub"]
        
        response = db.table("system_settings").update(update_data).eq("setting_key", setting_key).execute()
        return SystemSettingResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/system/bulk", response_model=dict)
async def bulk_update_settings(
    bulk_data: BulkSettingsUpdate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Bulk update multiple settings"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        updated = []
        
        for key, value in bulk_data.settings.items():
            try:
                response = db.table("system_settings").update({
                    "setting_value": value,
                    "updated_by": current_user["sub"]
                }).eq("setting_key", key).execute()
                if response.data:
                    updated.append(key)
            except (KeyError, AttributeError, TypeError) as e:
                # Skip settings with invalid data structure
                logger.warning(f"Skipping setting {key} due to data error: {str(e)}")
                continue
            except Exception as e:
                # Log unexpected errors but continue processing other settings
                logger.error(f"Error updating setting {key}: {str(e)}")
                continue
        
        return {"message": f"Updated {len(updated)} settings", "updated_keys": updated}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Role Permissions ====================

@router.get("/permissions", response_model=list[RolePermissionResponse])
async def get_role_permissions(
    role: Optional[Literal['admin', 'principal', 'teacher', 'student', 'parent']] = Query(None),
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Get role permissions"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        query = db.table("role_permissions").select("*")
        
        if role:
            query = query.eq("role", role)
        
        response = query.execute()
        return [RolePermissionResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/permissions/{role}/{permission_key}", response_model=RolePermissionResponse)
async def update_role_permission(
    role: str,
    permission_key: str,
    permission_data: RolePermissionUpdate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Update a role permission"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if permission exists
        existing = db.table("role_permissions").select("*").eq("role", role).eq("permission_key", permission_key).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
        
        response = db.table("role_permissions").update(permission_data.model_dump()).eq("role", role).eq("permission_key", permission_key).execute()
        return RolePermissionResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Fee Structure ====================

@router.get("/fees", response_model=list[FeeStructureResponse])
async def get_fee_structure(
    class_level: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    active_only: bool = Query(True),
    current_user: dict = Depends(get_current_user)
):
    """Get fee structure"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        query = db.table("fee_structure").select("*")
        
        if class_level:
            query = query.eq("class_level", class_level)
        if academic_year:
            query = query.eq("academic_year", academic_year)
        if active_only:
            query = query.eq("is_active", True)
        
        response = query.execute()
        return [FeeStructureResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/fees", response_model=FeeStructureResponse, status_code=status.HTTP_201_CREATED)
async def create_fee_structure(
    fee_data: FeeStructureCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new fee structure"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        response = db.table("fee_structure").insert(fee_data.model_dump()).execute()
        return FeeStructureResponse(**response.data[0])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/fees/{fee_id}", response_model=FeeStructureResponse)
async def update_fee_structure(
    fee_id: str,
    fee_data: FeeStructureUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update a fee structure"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if fee exists
        existing = db.table("fee_structure").select("*").eq("id", fee_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee structure not found")
        
        update_data = {k: v for k, v in fee_data.model_dump().items() if v is not None}
        response = db.table("fee_structure").update(update_data).eq("id", fee_id).execute()
        
        return FeeStructureResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/fees/{fee_id}")
async def delete_fee_structure(
    fee_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete a fee structure"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        existing = db.table("fee_structure").select("*").eq("id", fee_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee structure not found")
        
        db.table("fee_structure").delete().eq("id", fee_id).execute()
        return {"message": "Fee structure deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Academic Years ====================

@router.get("/academic-years", response_model=list[AcademicYearResponse])
async def get_academic_years(
    current_only: bool = Query(False),
    current_user: dict = Depends(get_current_user)
):
    """Get academic years"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin", "principal"])
        query = db.table("academic_years").select("*")
        
        if current_only:
            query = query.eq("is_current", True)
        
        response = query.order("start_date", desc=True).execute()
        return [AcademicYearResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/academic-years", response_model=AcademicYearResponse, status_code=status.HTTP_201_CREATED)
async def create_academic_year(
    year_data: AcademicYearCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new academic year"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # If this is set as current, unset all others
        if year_data.is_current:
            db.table("academic_years").update({"is_current": False}).eq("is_current", True).execute()
        
        response = db.table("academic_years").insert(year_data.model_dump()).execute()
        return AcademicYearResponse(**response.data[0])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/academic-years/{year_id}", response_model=AcademicYearResponse)
async def update_academic_year(
    year_id: str,
    year_data: AcademicYearUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update an academic year"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if year exists
        existing = db.table("academic_years").select("*").eq("id", year_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
        
        # If setting as current, unset all others
        if year_data.is_current:
            db.table("academic_years").update({"is_current": False}).eq("is_current", True).execute()
        
        update_data = {k: v for k, v in year_data.model_dump().items() if v is not None}
        response = db.table("academic_years").update(update_data).eq("id", year_id).execute()
        
        return AcademicYearResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Export All Settings ====================

@router.get("/export", response_model=SettingsExport)
async def export_all_settings(
    current_user: dict = Depends(require_role(["admin"]))
):
    """Export all settings for backup/review"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Get all settings
        settings_response = db.table("system_settings").select("*").execute()
        settings_by_category = {
            'general': {},
            'academic': {},
            'financial': {},
            'security': {},
            'notification': {},
            'appearance': {}
        }
        for setting in settings_response.data:
            settings_by_category[setting['category']][setting['setting_key']] = setting['setting_value']
        
        # Get all permissions
        permissions_response = db.table("role_permissions").select("*").execute()
        permissions_by_role = {}
        for perm in permissions_response.data:
            if perm['role'] not in permissions_by_role:
                permissions_by_role[perm['role']] = {}
            permissions_by_role[perm['role']][perm['permission_key']] = perm['permission_value']
        
        # Get fee structure
        fees_response = db.table("fee_structure").select("*").execute()
        fee_structure = [FeeStructureResponse(**fee) for fee in fees_response.data]
        
        # Get academic years
        years_response = db.table("academic_years").select("*").execute()
        academic_years = [AcademicYearResponse(**year) for year in years_response.data]
        
        return SettingsExport(
            general=settings_by_category['general'],
            academic=settings_by_category['academic'],
            financial=settings_by_category['financial'],
            security=settings_by_category['security'],
            notification=settings_by_category['notification'],
            appearance=settings_by_category['appearance'],
            permissions=permissions_by_role,
            fee_structure=fee_structure,
            academic_years=academic_years
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



