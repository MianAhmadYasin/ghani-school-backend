from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from app.models.syllabus import (
    SyllabusCreate, SyllabusUpdate, SyllabusResponse, SyllabusStats
)
from app.core.supabase import get_request_scoped_client
from app.core.security import get_current_user, require_role

router = APIRouter()


@router.get("", response_model=List[SyllabusResponse])
async def get_syllabuses(
    class_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """Get syllabuses with optional filters"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        query = db.table("syllabuses").select("*")
        
        if class_id:
            query = query.eq("class_id", class_id)
        
        if subject:
            query = query.eq("subject", subject)
        
        if term:
            query = query.eq("term", term)
        
        if year:
            query = query.eq("year", year)
        
        query = query.order("year", desc=True).order("term").limit(limit).offset(offset)
        
        response = query.execute()
        return [SyllabusResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/class/{class_id}", response_model=List[SyllabusResponse])
async def get_class_syllabuses(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all syllabuses for a specific class"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        response = db.table("syllabuses").select("*").eq("class_id", class_id).order("year", desc=True).order("term").execute()
        return [SyllabusResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{syllabus_id}", response_model=SyllabusResponse)
async def get_syllabus(
    syllabus_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific syllabus"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        response = db.table("syllabuses").select("*").eq("id", syllabus_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus not found")
        
        return SyllabusResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("", response_model=SyllabusResponse, status_code=status.HTTP_201_CREATED)
async def create_syllabus(
    syllabus_data: SyllabusCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Upload a new syllabus (admin/principal/teacher only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        syllabus_dict = syllabus_data.model_dump()
        syllabus_dict["uploaded_by"] = current_user.get("sub")
        
        from datetime import datetime
        if "upload_date" not in syllabus_dict or not syllabus_dict["upload_date"]:
            syllabus_dict["upload_date"] = datetime.now().isoformat()
        
        response = db.table("syllabuses").insert(syllabus_dict).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create syllabus")
        
        return SyllabusResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{syllabus_id}", response_model=SyllabusResponse)
async def update_syllabus(
    syllabus_id: str,
    syllabus_data: SyllabusUpdate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Update a syllabus (admin/principal/teacher only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if syllabus exists and user has permission
        check_response = db.table("syllabuses").select("*").eq("id", syllabus_id).execute()
        
        if not check_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus not found")
        
        syllabus = check_response.data[0]
        
        # Teachers can only update their own uploads
        if current_user.get("role") == "teacher" and syllabus["uploaded_by"] != current_user.get("sub"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own syllabuses")
        
        update_dict = syllabus_data.model_dump(exclude_unset=True)
        
        response = db.table("syllabuses").update(update_dict).eq("id", syllabus_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update syllabus")
        
        return SyllabusResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{syllabus_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_syllabus(
    syllabus_id: str,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Delete a syllabus (admin/principal/teacher only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if syllabus exists and user has permission
        check_response = db.table("syllabuses").select("*").eq("id", syllabus_id).execute()
        
        if not check_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus not found")
        
        syllabus = check_response.data[0]
        
        # Teachers can only delete their own uploads
        if current_user.get("role") == "teacher" and syllabus["uploaded_by"] != current_user.get("sub"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own syllabuses")
        
        db.table("syllabuses").delete().eq("id", syllabus_id).execute()
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/stats/overview", response_model=SyllabusStats)
async def get_syllabus_stats(
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Get syllabus statistics (admin/principal only)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        response = db.table("syllabuses").select("*").execute()
        syllabuses = response.data
        
        total = len(syllabuses)
        
        # Count by term
        by_term = {}
        for s in syllabuses:
            term = s.get("term", "unknown")
            by_term[term] = by_term.get(term, 0) + 1
        
        # Count by class
        by_class = {}
        for s in syllabuses:
            class_name = s.get("class_name", "unknown")
            by_class[class_name] = by_class.get(class_name, 0) + 1
        
        # Count by subject
        by_subject = {}
        for s in syllabuses:
            subject = s.get("subject", "unknown")
            by_subject[subject] = by_subject.get(subject, 0) + 1
        
        # Recent uploads (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        recent_uploads = sum(1 for s in syllabuses 
                            if s.get("upload_date") and s.get("upload_date") >= thirty_days_ago)
        
        return SyllabusStats(
            total_syllabuses=total,
            syllabuses_by_term=by_term,
            syllabuses_by_class=by_class,
            syllabuses_by_subject=by_subject,
            recent_uploads=recent_uploads
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))









