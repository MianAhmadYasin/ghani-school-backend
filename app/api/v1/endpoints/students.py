from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.student import StudentCreate, StudentUpdate, StudentResponse
from app.models.user import UserResponse
from app.core.supabase import supabase, supabase_admin, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.core.logging_config import get_logger
from app.core.response_helpers import populate_student_user_data

router = APIRouter()
logger = get_logger(__name__)


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new student"""
    try:
        # Create user account
        auth_response = supabase_admin.auth.admin.create_user({
            "email": student_data.email,
            "password": student_data.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": student_data.full_name,
                "role": "student"
            }
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create student account"
            )
        
        user_id = auth_response.user.id
        
        # Create profile
        profile_data = {
            "user_id": user_id,
            "full_name": student_data.full_name,
            "phone": student_data.phone,
            "address": student_data.address,
        }
        db = get_request_scoped_client(current_user.get("access_token"), True)
        db.table("profiles").insert(profile_data).execute()
        
        # Create student record
        student_record = {
            "user_id": user_id,
            "admission_number": student_data.admission_number,
            "admission_date": student_data.admission_date,  # Already a string from frontend
            "class_id": student_data.class_id,
            "guardian_info": student_data.guardian_info.model_dump(),
            "status": "active"
        }
        
        response = db.table("students").insert(student_record).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create student record"
            )
        
        student = response.data[0]
        
        # Populate user data
        students_data = populate_student_user_data(
            [student], 
            db, 
            current_user
        )
        student = students_data[0] if students_data else student
        
        return StudentResponse(**student)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create student: {str(e)}")
        error_msg = str(e)
        # Provide more specific error messages
        if "email" in error_msg.lower() and "already" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists"
            )
        elif "admission_number" in error_msg.lower() and "unique" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A student with this admission number already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create student: {error_msg}"
        )


@router.get("", response_model=list[StudentResponse])
async def list_students(
    class_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List all students with optional filters"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        query = db.table("students").select("*")
        
        if class_id:
            query = query.eq("class_id", class_id)
        
        if status:
            query = query.eq("status", status)
        
        if search:
            # Search by admission number
            query = query.ilike("admission_number", f"%{search}%")
        
        query = query.range(offset, offset + limit - 1)
        response = query.execute()
        
        # Populate user data for each student
        students_data = populate_student_user_data(
            response.data, 
            db, 
            current_user
        )
        
        return [StudentResponse(**student) for student in students_data]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch students: {str(e)}"
        )


@router.get("/me/profile")
async def get_my_student_profile(
    current_user: dict = Depends(require_role(["student"]))
):
    """Get current student's profile"""
    try:
        user_id = current_user["sub"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        response = db.table("students").select("*").eq("user_id", user_id).single().execute()
        student = response.data
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        
        # Get user profile
        profile_response = db.table("profiles").select("*").eq("user_id", user_id).single().execute()
        profile = profile_response.data
        
        student_response = StudentResponse(**student)
        if profile:
            student_response.user = UserResponse(
                id=user_id,
                email=current_user["email"],
                full_name=profile.get("full_name", ""),
                role="student",
                phone=profile.get("phone"),
                address=profile.get("address"),
                avatar_url=profile.get("avatar_url"),
                created_at=profile.get("created_at")
            )
        
        return student_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch student profile: {str(e)}"
        )


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get student by ID"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        response = db.table("students").select("*").eq("id", student_id).single().execute()
        student = response.data
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        # Populate user data
        students_data = populate_student_user_data(
            [student], 
            db, 
            current_user
        )
        student = students_data[0] if students_data else student
        
        return StudentResponse(**student)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch student: {str(e)}"
        )


@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    student_data: StudentUpdate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Update student information"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        
        # Get student to find user_id
        student_response = db.table("students").select("*").eq("id", student_id).single().execute()
        student = student_response.data
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        # Update profile if needed
        if student_data.full_name or student_data.phone or student_data.address:
            profile_update = {}
            if student_data.full_name:
                profile_update["full_name"] = student_data.full_name
            if student_data.phone:
                profile_update["phone"] = student_data.phone
            if student_data.address:
                profile_update["address"] = student_data.address
            
            if profile_update:
                db.table("profiles").update(profile_update).eq("user_id", student["user_id"]).execute()
        
        # Update student record
        update_data = student_data.model_dump(exclude_unset=True, exclude={"full_name", "phone", "address"})
        
        if "guardian_info" in update_data:
            update_data["guardian_info"] = update_data["guardian_info"].model_dump()
        
        if update_data:
            response = db.table("students").update(update_data).eq("id", student_id).execute()
            updated_student = response.data[0]
            
            # Populate user data
            students_data = populate_student_user_data(
                [updated_student], 
                db, 
                current_user
            )
            updated_student = students_data[0] if students_data else updated_student
            
            return StudentResponse(**updated_student)
        
        # Populate user data for existing student
        students_data = populate_student_user_data(
            [student], 
            db, 
            current_user
        )
        student = students_data[0] if students_data else student
        
        return StudentResponse(**student)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update student: {str(e)}"
        )


@router.delete("/{student_id}")
async def delete_student(
    student_id: str,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Deactivate student"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        # Update status to inactive
        db.table("students").update({"status": "inactive"}).eq("id", student_id).execute()
        
        return {"message": "Student deactivated successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to deactivate student: {str(e)}"
        )



