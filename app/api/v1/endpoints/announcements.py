"""
Announcements API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from app.core.supabase import supabase_admin, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.models.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse

router = APIRouter()

@router.get("", response_model=List[AnnouncementResponse])
async def list_announcements(
    target_audience: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List announcements with optional filters"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        query = db.table("announcements").select("*")
        
        if target_audience:
            query = query.eq("target_audience", target_audience)
        
        if priority:
            query = query.eq("priority", priority)
        
        if is_active is not None:
            query = query.eq("is_active", is_active)
        
        query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
        response = query.execute()
        
        return [AnnouncementResponse(**announcement) for announcement in response.data]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch announcements: {str(e)}"
        )

@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    announcement_data: AnnouncementCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new announcement"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        announcement_record = announcement_data.model_dump()
        announcement_record["created_by"] = current_user["sub"]
        
        response = db.table("announcements").insert(announcement_record).execute()
        announcement = response.data[0]
        
        return AnnouncementResponse(**announcement)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create announcement: {str(e)}"
        )

@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific announcement"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        response = db.table("announcements").select("*").eq("id", announcement_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )
        
        return AnnouncementResponse(**response.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch announcement: {str(e)}"
        )

@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: str,
    announcement_data: AnnouncementUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update an announcement"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        update_data = announcement_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )
        
        response = db.table("announcements").update(update_data).eq("id", announcement_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )
        
        return AnnouncementResponse(**response.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update announcement: {str(e)}"
        )

@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    announcement_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete an announcement"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        response = db.table("announcements").delete().eq("id", announcement_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete announcement: {str(e)}"
        )
