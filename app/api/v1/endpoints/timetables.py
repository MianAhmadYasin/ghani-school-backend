from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from app.models.timetable import (
    TimetableCreate, TimetableUpdate, TimetableResponse,
    TimetableEntryCreate, TimetableEntryUpdate, TimetableEntryResponse
)
from app.core.supabase import get_request_scoped_client
from app.core.security import get_current_user, require_role

router = APIRouter()


# ==================== Timetables ====================

@router.get("", response_model=List[TimetableResponse])
async def get_timetables(
    class_id: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """Get timetables with optional filters"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        query = db.table("timetables").select("*")
        
        if class_id:
            query = query.eq("class_id", class_id)
        
        if status_filter:
            query = query.eq("status", status_filter)
        
        # Filter by teacher if provided (via timetable_entries)
        if teacher_id:
            # Get timetable IDs that have entries for this teacher
            entries_response = db.table("timetable_entries").select("timetable_id").eq("teacher_id", teacher_id).execute()
            timetable_ids = list(set([e["timetable_id"] for e in entries_response.data]))
            if timetable_ids:
                query = query.in_("id", timetable_ids)
            else:
                return []  # No timetables for this teacher
        
        query = query.order("created_at", desc=True).limit(limit).offset(offset)
        
        response = query.execute()
        return [TimetableResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/class/{class_id}", response_model=TimetableResponse)
async def get_class_timetable(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get timetable for a specific class (prioritizes final status)"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # Try to get final status first
        response = db.table("timetables").select("*").eq("class_id", class_id).eq("status", "final").execute()
        
        if not response.data:
            # If no final, get any timetable for the class
            response = db.table("timetables").select("*").eq("class_id", class_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No timetable found for this class")
        
        return TimetableResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/teacher/{teacher_id}", response_model=List[TimetableResponse])
async def get_teacher_timetables(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all timetables for a teacher"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # Get timetable IDs from entries
        entries_response = db.table("timetable_entries").select("timetable_id").eq("teacher_id", teacher_id).execute()
        timetable_ids = list(set([e["timetable_id"] for e in entries_response.data]))
        
        if not timetable_ids:
            return []
        
        response = db.table("timetables").select("*").in_("id", timetable_ids).execute()
        return [TimetableResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{timetable_id}", response_model=TimetableResponse)
async def get_timetable(
    timetable_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific timetable with all entries"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        response = db.table("timetables").select("*").eq("id", timetable_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable not found")
        
        return TimetableResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("", response_model=TimetableResponse, status_code=status.HTTP_201_CREATED)
async def create_timetable(
    timetable_data: TimetableCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new timetable (admin/principal only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        timetable_dict = timetable_data.model_dump()
        timetable_dict["created_by"] = current_user.get("sub")
        
        response = db.table("timetables").insert(timetable_dict).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create timetable")
        
        return TimetableResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{timetable_id}", response_model=TimetableResponse)
async def update_timetable(
    timetable_id: str,
    timetable_data: TimetableUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update a timetable (admin/principal only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        update_dict = timetable_data.model_dump(exclude_unset=True)
        
        response = db.table("timetables").update(update_dict).eq("id", timetable_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable not found")
        
        return TimetableResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{timetable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete a timetable and all its entries (admin/principal only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Delete entries first (CASCADE should handle this, but being explicit)
        db.table("timetable_entries").delete().eq("timetable_id", timetable_id).execute()
        
        # Delete timetable
        db.table("timetables").delete().eq("id", timetable_id).execute()
        
        return None
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Timetable Entries ====================

@router.get("/{timetable_id}/entries", response_model=List[TimetableEntryResponse])
async def get_timetable_entries(
    timetable_id: str,
    day_of_week: Optional[int] = Query(None, ge=1, le=7),
    current_user: dict = Depends(get_current_user)
):
    """Get all entries for a timetable"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        query = db.table("timetable_entries").select("*").eq("timetable_id", timetable_id)
        
        if day_of_week:
            query = query.eq("day_of_week", day_of_week)
        
        query = query.order("day_of_week").order("period_number")
        
        response = query.execute()
        return [TimetableEntryResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{timetable_id}/entries", response_model=TimetableEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_timetable_entry(
    timetable_id: str,
    entry_data: TimetableEntryCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new timetable entry (admin/principal only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        entry_dict = entry_data.model_dump()
        entry_dict["timetable_id"] = timetable_id
        
        response = db.table("timetable_entries").insert(entry_dict).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create timetable entry")
        
        return TimetableEntryResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/entries/{entry_id}", response_model=TimetableEntryResponse)
async def update_timetable_entry(
    entry_id: str,
    entry_data: TimetableEntryUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update a timetable entry (admin/principal only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        update_dict = entry_data.model_dump(exclude_unset=True)
        
        response = db.table("timetable_entries").update(update_dict).eq("id", entry_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable entry not found")
        
        return TimetableEntryResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timetable_entry(
    entry_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete a timetable entry (admin/principal only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        db.table("timetable_entries").delete().eq("id", entry_id).execute()
        
        return None
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))









