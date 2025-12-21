from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from app.models.notification import (
    NotificationCreate, NotificationUpdate, NotificationResponse, NotificationStats
)
from app.core.supabase import get_request_scoped_client
from app.core.security import get_current_user, require_role

router = APIRouter()


@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = Query(False, description="Filter unread notifications only"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """Get current user's notifications"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        query = db.table("notifications").select("*").eq("user_id", current_user.get("sub"))
        
        if unread_only:
            query = query.is_("read_at", "null")
        
        query = query.order("created_at", desc=True).limit(limit).offset(offset)
        
        response = query.execute()
        return [NotificationResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/all", response_model=List[NotificationResponse])
async def get_all_notifications(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Get all notifications (admin only)"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            True  # Admin always uses service role
        )
        
        query = db.table("notifications").select("*")
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        query = query.order("created_at", desc=True).limit(limit).offset(offset)
        
        response = query.execute()
        return [NotificationResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get notification statistics for current user"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # Get all notifications for user
        all_notifications = db.table("notifications").select("*").eq("user_id", current_user.get("sub")).execute()
        
        total = len(all_notifications.data)
        unread_count = sum(1 for n in all_notifications.data if n.get("read_at") is None)
        read_count = total - unread_count
        
        return NotificationStats(
            total_notifications=total,
            unread_count=unread_count,
            read_count=read_count,
            notifications_by_type={}
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific notification"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        response = db.table("notifications").select("*").eq("id", notification_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        
        notification = response.data[0]
        
        # Check if user owns this notification or is admin
        if notification["user_id"] != current_user.get("sub") and current_user.get("role") not in ["admin", "principal"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        return NotificationResponse(**notification)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_data: NotificationCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new notification (admin only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        notification_dict = notification_data.model_dump()
        notification_dict["read_at"] = None
        
        response = db.table("notifications").insert(notification_dict).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create notification")
        
        return NotificationResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # First check if notification exists and belongs to user
        check_response = db.table("notifications").select("*").eq("id", notification_id).execute()
        
        if not check_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        
        notification = check_response.data[0]
        
        if notification["user_id"] != current_user.get("sub"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        # Update read_at
        from datetime import datetime, timezone
        update_data = {"read_at": datetime.now(timezone.utc).isoformat()}
        
        response = db.table("notifications").update(update_data).eq("id", notification_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update notification")
        
        return NotificationResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: str,
    notification_data: NotificationUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a notification"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # Check if notification exists
        check_response = db.table("notifications").select("*").eq("id", notification_id).execute()
        
        if not check_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        
        notification = check_response.data[0]
        
        # Only admins can update notifications they don't own
        if notification["user_id"] != current_user.get("sub") and current_user.get("role") not in ["admin", "principal"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        update_dict = notification_data.model_dump(exclude_unset=True)
        
        response = db.table("notifications").update(update_dict).eq("id", notification_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update notification")
        
        return NotificationResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a notification"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # Check if notification exists
        check_response = db.table("notifications").select("*").eq("id", notification_id).execute()
        
        if not check_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        
        notification = check_response.data[0]
        
        # Users can delete their own notifications, admins can delete any
        if notification["user_id"] != current_user.get("sub") and current_user.get("role") not in ["admin", "principal"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        db.table("notifications").delete().eq("id", notification_id).execute()
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))









