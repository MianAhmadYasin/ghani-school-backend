from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import datetime, date
from app.models.event import EventCreate, EventUpdate, EventResponse, EventStats
from app.core.supabase import supabase_admin, get_request_scoped_client
from app.core.security import get_current_user, require_role

router = APIRouter()


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new event"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        event_record = {
            "title": event_data.title,
            "description": event_data.description,
            "date": event_data.date.isoformat(),
            "time": event_data.time,
            "location": event_data.location,
            "type": event_data.type,
            "status": event_data.status,
            "created_by": current_user["sub"]
        }
        
        response = db.table("events").insert(event_record).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create event"
            )
        
        return response.data[0]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create event: {str(e)}"
        )


@router.get("", response_model=list[EventResponse])
async def list_events(
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List all events with filters"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        query = db.table("events").select("*")
        
        if type:
            query = query.eq("type", type)
        
        if status:
            query = query.eq("status", status)
        
        if date_from:
            query = query.gte("date", date_from)
        
        if date_to:
            query = query.lte("date", date_to)
        
        response = query.order("date", desc=True).range(offset, offset + limit - 1).execute()
        
        return response.data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch events: {str(e)}"
        )


@router.get("/stats", response_model=EventStats)
async def get_event_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get event statistics"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        # Get all events
        all_events = db.table("events").select("*").execute()
        events = all_events.data
        
        # Calculate stats
        total_events = len(events)
        upcoming_events = len([e for e in events if e.get("status") == "upcoming"])
        ongoing_events = len([e for e in events if e.get("status") == "ongoing"])
        completed_events = len([e for e in events if e.get("status") == "completed"])
        
        # Events by type
        events_by_type = {}
        for event in events:
            event_type = event.get("type", "other")
            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
        
        # Events this month
        current_month = datetime.now().month
        current_year = datetime.now().year
        events_this_month = len([
            e for e in events 
            if e.get("date") and 
            datetime.fromisoformat(e["date"]).month == current_month and
            datetime.fromisoformat(e["date"]).year == current_year
        ])
        
        return EventStats(
            total_events=total_events,
            upcoming_events=upcoming_events,
            ongoing_events=ongoing_events,
            completed_events=completed_events,
            events_by_type=events_by_type,
            events_this_month=events_this_month
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch event stats: {str(e)}"
        )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific event"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        response = db.table("events").select("*").eq("id", event_id).single().execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        return response.data
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch event: {str(e)}"
        )


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    event_data: EventUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update an event"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        update_data = event_data.model_dump(exclude_unset=True)
        
        # Convert date to ISO format if present
        if "date" in update_data and update_data["date"]:
            update_data["date"] = update_data["date"].isoformat()
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        response = db.table("events").update(update_data).eq("id", event_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        return response.data[0]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update event: {str(e)}"
        )


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete an event"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        response = db.table("events").delete().eq("id", event_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        return None
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete event: {str(e)}"
        )
