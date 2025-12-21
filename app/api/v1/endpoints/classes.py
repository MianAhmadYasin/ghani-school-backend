from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.class_model import (
    ClassCreate, ClassUpdate, ClassResponse,
    AssignTeacherRequest, AddStudentsRequest
)
from app.core.supabase import supabase, get_request_scoped_client
from app.core.supabase_helpers import get_db_client
from app.core.security import get_current_user, require_role

router = APIRouter()


@router.post("", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new class"""
    try:
        db = get_db_client(current_user, is_admin_operation=True)
        class_record = class_data.model_dump()
        response = db.table("classes").insert(class_record).execute()
        
        return ClassResponse(**response.data[0])
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create class: {str(e)}"
        )


@router.get("", response_model=list[ClassResponse])
async def list_classes(
    academic_year: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List all classes with optional filters"""
    try:
        db = get_db_client(current_user, is_admin_operation=current_user.get("role") in ["admin","principal"])
        query = db.table("classes").select("*")
        
        if academic_year:
            query = query.eq("academic_year", academic_year)
        
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        
        query = query.range(offset, offset + limit - 1)
        response = query.execute()
        
        return [ClassResponse(**cls) for cls in response.data]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch classes: {str(e)}"
        )


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get class by ID"""
    try:
        db = get_db_client(current_user, is_admin_operation=current_user.get("role") in ["admin","principal"])
        response = db.table("classes").select("*").eq("id", class_id).single().execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )
        
        return ClassResponse(**response.data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch class: {str(e)}"
        )


@router.get("/{class_id}/students")
async def get_class_students(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all students in a class"""
    try:
        db = get_db_client(current_user, is_admin_operation=current_user.get("role") in ["admin","principal"])
        response = db.table("students").select("*").eq("class_id", class_id).execute()
        
        return response.data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch class students: {str(e)}"
        )


@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: str,
    class_data: ClassUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update class information"""
    try:
        db = get_db_client(current_user, is_admin_operation=True)
        update_data = class_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data provided for update"
            )
        
        response = db.table("classes").update(update_data).eq("id", class_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )
        
        return ClassResponse(**response.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update class: {str(e)}"
        )


@router.post("/{class_id}/assign-teacher")
async def assign_teacher(
    class_id: str,
    request: AssignTeacherRequest,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Assign teacher to class"""
    try:
        db = get_db_client(current_user, is_admin_operation=True)
        # Verify teacher exists
        teacher_response = db.table("teachers").select("id").eq("id", request.teacher_id).single().execute()
        
        if not teacher_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found"
            )
        
        # Update class
        response = db.table("classes").update({
            "teacher_id": request.teacher_id
        }).eq("id", class_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )
        
        return {"message": "Teacher assigned successfully", "class": response.data[0]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to assign teacher: {str(e)}"
        )


@router.post("/{class_id}/add-students")
async def add_students_to_class(
    class_id: str,
    request: AddStudentsRequest,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Add students to class"""
    try:
        db = get_db_client(current_user, is_admin_operation=True)
        # Update students
        for student_id in request.student_ids:
            db.table("students").update({
                "class_id": class_id
            }).eq("id", student_id).execute()
        
        return {"message": f"Added {len(request.student_ids)} students to class"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add students to class: {str(e)}"
        )


@router.post("/{class_id}/remove-student")
async def remove_student_from_class(
    class_id: str,
    request: dict,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Remove student from class"""
    try:
        db = get_db_client(current_user, is_admin_operation=True)
        student_id = request.get("student_id")
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="student_id is required"
            )
        
        # Update student to remove class assignment
        db.table("students").update({
            "class_id": None
        }).eq("id", student_id).execute()
        
        return {"message": "Student removed from class successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to remove student from class: {str(e)}"
        )


@router.delete("/{class_id}")
async def delete_class(
    class_id: str,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Delete class"""
    try:
        db = get_db_client(current_user, is_admin_operation=True)
        # Check if class has students
        students_response = db.table("students").select("id").eq("class_id", class_id).execute()
        
        if students_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete class with enrolled students. Please remove students first."
            )
        
        db.table("classes").delete().eq("id", class_id).execute()
        
        return {"message": "Class deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete class: {str(e)}"
        )



