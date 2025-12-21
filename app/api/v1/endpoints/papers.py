"""
Papers/Exam Papers API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from typing import List, Optional
import uuid
from datetime import datetime

from app.core.supabase import supabase_admin, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.models.paper import (
    PaperCreate, PaperUpdate, PaperResponse, PaperStats, TermType
)
from app.models.exam import ApprovalStatus, PaperApprovalRequest

router = APIRouter()

@router.get("", response_model=List[PaperResponse])
async def list_papers(
    class_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    uploaded_by: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List papers with optional filters"""
    try:
        query = supabase_admin.table("papers").select("*")
        
        # If user is a teacher, only show their papers
        if current_user.get("role") == "teacher":
            query = query.eq("uploaded_by", current_user.get("sub") or current_user.get("id"))
        elif uploaded_by:
            query = query.eq("uploaded_by", uploaded_by)
        
        if class_id:
            query = query.eq("class_id", class_id)
        
        if subject:
            query = query.ilike("subject", f"%{subject}%")
        
        if term:
            query = query.eq("term", term)
        
        if year:
            query = query.eq("year", year)
        
        query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
        response = query.execute()
        
        papers_data = response.data or []
        
        # Fetch uploaded_by names from profiles table
        user_ids = list(set(p.get("uploaded_by") for p in papers_data if p.get("uploaded_by")))
        profiles_map = {}
        if user_ids:
            profiles_resp = supabase_admin.table("profiles").select("user_id, full_name").in_("user_id", user_ids).execute()
            profiles_map = {p.get("user_id"): p.get("full_name") for p in profiles_resp.data}
        
        papers = []
        for paper in papers_data:
            paper_dict = dict(paper)
            paper_dict["uploaded_by_name"] = profiles_map.get(paper.get("uploaded_by"))
            papers.append(PaperResponse(**paper_dict))
        
        return papers
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch papers: {str(e)}"
        )

@router.post("", response_model=PaperResponse, status_code=status.HTTP_201_CREATED)
async def create_paper(
    paper_data: PaperCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Create a new paper record"""
    try:
        paper_record = paper_data.model_dump()
        paper_record["uploaded_by"] = current_user.get("sub") or current_user.get("id")
        paper_record["upload_date"] = datetime.utcnow().isoformat()
        
        response = supabase_admin.table("papers").insert(paper_record).execute()
        paper = response.data[0]
        
        # Fetch user details from profiles
        user_id = current_user.get("sub") or current_user.get("id")
        profile_response = supabase_admin.table("profiles").select("full_name").eq("user_id", user_id).single().execute()
        if profile_response.data:
            paper["uploaded_by_name"] = profile_response.data.get("full_name")
        
        return PaperResponse(**paper)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create paper: {str(e)}"
        )

@router.get("/stats", response_model=PaperStats)
async def get_paper_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get paper statistics"""
    try:
        # Get all papers
        if current_user.get("role") == "teacher":
            user_id = current_user.get("sub") or current_user.get("id")
            query = supabase_admin.table("papers").select("*").eq("uploaded_by", user_id)
        else:
            query = supabase_admin.table("papers").select("*")
        
        response = query.execute()
        papers = response.data
        
        # Calculate statistics
        total_papers = len(papers)
        
        papers_by_term = {}
        papers_by_class = {}
        papers_by_subject = {}
        papers_by_year = {}
        
        for paper in papers:
            # By term
            term = paper.get("term", "unknown")
            papers_by_term[term] = papers_by_term.get(term, 0) + 1
            
            # By class
            class_name = paper.get("class_name", "unknown")
            papers_by_class[class_name] = papers_by_class.get(class_name, 0) + 1
            
            # By subject
            subject = paper.get("subject", "unknown")
            papers_by_subject[subject] = papers_by_subject.get(subject, 0) + 1
            
            # By year
            year = paper.get("year", 0)
            papers_by_year[str(year)] = papers_by_year.get(str(year), 0) + 1
        
        # Recent uploads (last 30 days)
        thirty_days_ago = datetime.utcnow().replace(day=1).isoformat()
        recent_uploads = len([p for p in papers if p.get("created_at", "") >= thirty_days_ago])
        
        return PaperStats(
            total_papers=total_papers,
            papers_by_term=papers_by_term,
            papers_by_class=papers_by_class,
            papers_by_subject=papers_by_subject,
            papers_by_year=papers_by_year,
            recent_uploads=recent_uploads
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch statistics: {str(e)}"
        )

@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific paper"""
    try:
        response = supabase_admin.table("papers").select("*").eq("id", paper_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        paper = response.data[0]
        
        # Check if user has permission to view
        user_id = current_user.get("sub") or current_user.get("id")
        if current_user.get("role") == "teacher" and paper.get("uploaded_by") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this paper"
            )
        
        # Fetch user details from profiles
        if paper.get("uploaded_by"):
            profile_response = supabase_admin.table("profiles").select("full_name").eq("user_id", paper.get("uploaded_by")).single().execute()
            if profile_response.data:
                paper["uploaded_by_name"] = profile_response.data.get("full_name")
        
        return PaperResponse(**paper)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch paper: {str(e)}"
        )

@router.put("/{paper_id}", response_model=PaperResponse)
async def update_paper(
    paper_id: str,
    paper_data: PaperUpdate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Update a paper"""
    try:
        # Check if paper exists and user has permission
        existing_paper = supabase_admin.table("papers").select("*").eq("id", paper_id).execute()
        
        if not existing_paper.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        # Teachers can only update their own papers
        user_id = current_user.get("sub") or current_user.get("id")
        if current_user.get("role") == "teacher" and existing_paper.data[0]["uploaded_by"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this paper"
            )
        
        update_data = paper_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )
        
        response = supabase_admin.table("papers").update(update_data).eq("id", paper_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        paper = response.data[0]
        
        # Fetch user details from profiles
        profile_response = supabase_admin.table("profiles").select("full_name").eq("user_id", paper.get("uploaded_by")).single().execute()
        if profile_response.data:
            paper["uploaded_by_name"] = profile_response.data.get("full_name")
        
        return PaperResponse(**paper)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update paper: {str(e)}"
        )

@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(
    paper_id: str,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Delete a paper"""
    try:
        # Check if paper exists and user has permission
        existing_paper = supabase_admin.table("papers").select("*").eq("id", paper_id).execute()
        
        if not existing_paper.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        # Teachers can only delete their own papers
        user_id = current_user.get("sub") or current_user.get("id")
        if current_user.get("role") == "teacher" and existing_paper.data[0]["uploaded_by"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this paper"
            )
        
        response = supabase_admin.table("papers").delete().eq("id", paper_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete paper: {str(e)}"
        )

@router.get("/class/{class_id}/summary")
async def get_class_paper_summary(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get summary of papers for a specific class"""
    try:
        response = supabase_admin.table("papers").select("*").eq("class_id", class_id).execute()
        papers = response.data
        
        summary = {
            "total": len(papers),
            "by_term": {},
            "by_subject": {},
            "by_year": {}
        }
        
        for paper in papers:
            term = paper.get("term", "unknown")
            summary["by_term"][term] = summary["by_term"].get(term, 0) + 1
            
            subject = paper.get("subject", "unknown")
            summary["by_subject"][subject] = summary["by_subject"].get(subject, 0) + 1
            
            year = paper.get("year", 0)
            summary["by_year"][str(year)] = summary["by_year"].get(str(year), 0) + 1
        
        return summary
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch summary: {str(e)}"
        )


@router.post("/{paper_id}/submit")
async def submit_paper_for_approval(
    paper_id: str,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Submit paper for approval"""
    try:
        # Check if paper exists
        existing_paper = supabase_admin.table("papers").select("*").eq("id", paper_id).execute()
        
        if not existing_paper.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        paper = existing_paper.data[0]
        
        # Teachers can only submit their own papers
        user_id = current_user.get("sub") or current_user.get("id")
        if current_user.get("role") == "teacher" and paper["uploaded_by"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only submit your own papers for approval"
            )
        
        # Update paper status to pending
        update_data = {
            "approval_status": "pending",
            "submitted_for_approval_at": datetime.utcnow().isoformat()
        }
        
        response = supabase_admin.table("papers").update(update_data).eq("id", paper_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        return {"message": "Paper submitted for approval successfully", "paper": response.data[0]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to submit paper: {str(e)}"
        )


@router.post("/{paper_id}/approve")
async def approve_paper(
    paper_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Approve a paper (principal/admin only)"""
    try:
        # Check if paper exists
        existing_paper = supabase_admin.table("papers").select("*").eq("id", paper_id).execute()
        
        if not existing_paper.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        paper = existing_paper.data[0]
        
        if paper.get("approval_status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Paper is not in pending status. Current status: {paper.get('approval_status')}"
            )
        
        # Update paper status to approved
        user_id = current_user.get("sub") or current_user.get("id")
        update_data = {
            "approval_status": "approved",
            "approved_by": user_id,
            "approved_at": datetime.utcnow().isoformat()
        }
        
        response = supabase_admin.table("papers").update(update_data).eq("id", paper_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        return {"message": "Paper approved successfully", "paper": response.data[0]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to approve paper: {str(e)}"
        )


@router.post("/{paper_id}/reject")
async def reject_paper(
    paper_id: str,
    approval_request: PaperApprovalRequest,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Reject a paper with reason (principal/admin only)"""
    try:
        # Check if paper exists
        existing_paper = supabase_admin.table("papers").select("*").eq("id", paper_id).execute()
        
        if not existing_paper.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        paper = existing_paper.data[0]
        
        if paper.get("approval_status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Paper is not in pending status. Current status: {paper.get('approval_status')}"
            )
        
        if not approval_request.rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required"
            )
        
        # Update paper status to rejected
        user_id = current_user.get("sub") or current_user.get("id")
        update_data = {
            "approval_status": "rejected",
            "rejected_by": user_id,
            "rejection_reason": approval_request.rejection_reason
        }
        
        response = supabase_admin.table("papers").update(update_data).eq("id", paper_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        return {"message": "Paper rejected", "paper": response.data[0]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to reject paper: {str(e)}"
        )


@router.get("/pending/list")
async def get_pending_papers(
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Get papers pending approval"""
    try:
        query = supabase_admin.table("papers").select("*").eq("approval_status", "pending")
        
        # Teachers only see their own pending papers
        if current_user.get("role") == "teacher":
            user_id = current_user.get("sub") or current_user.get("id")
            query = query.eq("uploaded_by", user_id)
        
        query = query.order("submitted_for_approval_at", desc=True).range(offset, offset + limit - 1)
        response = query.execute()
        
        papers_data = response.data or []
        
        # Fetch uploaded_by names
        user_ids = list(set(p.get("uploaded_by") for p in papers_data if p.get("uploaded_by")))
        profiles_map = {}
        if user_ids:
            profiles_resp = supabase_admin.table("profiles").select("user_id, full_name").in_("user_id", user_ids).execute()
            profiles_map = {p.get("user_id"): p.get("full_name") for p in profiles_resp.data}
        
        papers = []
        for paper in papers_data:
            paper_dict = dict(paper)
            paper_dict["uploaded_by_name"] = profiles_map.get(paper.get("uploaded_by"))
            papers.append(paper_dict)
        
        return {"papers": papers, "count": len(papers)}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch pending papers: {str(e)}"
        )

