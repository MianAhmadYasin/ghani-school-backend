from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import date
from app.models.teacher import TeacherCreate, TeacherUpdate, TeacherResponse
from app.core.supabase import supabase, supabase_admin, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.core.logging_config import get_logger
from app.core.response_helpers import populate_teacher_user_data

router = APIRouter()
logger = get_logger(__name__)


@router.post("", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
async def create_teacher(
    teacher_data: TeacherCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new teacher"""
    try:
        # Create user account
        auth_response = supabase_admin.auth.admin.create_user({
            "email": teacher_data.email,
            "password": teacher_data.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": teacher_data.full_name,
                "role": "teacher"
            }
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create teacher account"
            )
        
        user_id = auth_response.user.id
        
        # Create profile
        profile_data = {
            "user_id": user_id,
            "full_name": teacher_data.full_name,
            "phone": teacher_data.phone,
            "address": teacher_data.address,
        }
        db = get_request_scoped_client(current_user.get("access_token"), True)
        db.table("profiles").insert(profile_data).execute()
        
        # Create teacher record
        # Handle join_date - convert date object to ISO string if needed
        join_date_value = teacher_data.join_date
        if isinstance(join_date_value, date):
            join_date_value = join_date_value.isoformat()
        elif not isinstance(join_date_value, str):
            join_date_value = str(join_date_value)
        
        teacher_record = {
            "user_id": user_id,
            "employee_id": teacher_data.employee_id,
            "join_date": join_date_value,
            "qualification": teacher_data.qualification,
            "subjects": teacher_data.subjects,
            "salary_info": teacher_data.salary_info.model_dump(),
            "status": "active",
            "cnic_number": teacher_data.cnic_number,
            "experience_years": teacher_data.experience_years or 0,
            "contact_number": teacher_data.contact_number,
            "home_address": teacher_data.home_address,
            "cnic_copy_url": teacher_data.cnic_copy_url,
            "degree_copy_url": teacher_data.degree_copy_url,
            "remarks": teacher_data.remarks
        }
        # Remove None values
        teacher_record = {k: v for k, v in teacher_record.items() if v is not None}
        
        response = db.table("teachers").insert(teacher_record).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create teacher record"
            )
        
        teacher = response.data[0]
        
        # Populate user data
        teachers_data = populate_teacher_user_data(
            [teacher], 
            db, 
            current_user
        )
        teacher = teachers_data[0] if teachers_data else teacher
        
        return TeacherResponse(**teacher)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create teacher: {str(e)}")
        error_msg = str(e)
        # Provide more specific error messages
        if "email" in error_msg.lower() and "already" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists"
            )
        elif "employee_id" in error_msg.lower() and "unique" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A teacher with this employee ID already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create teacher: {error_msg}"
        )


@router.get("", response_model=list[TeacherResponse])
async def list_teachers(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List all teachers with optional filters"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        query = db.table("teachers").select("*")
        
        if status:
            query = query.eq("status", status)
        
        if search:
            query = query.ilike("employee_id", f"%{search}%")
        
        query = query.range(offset, offset + limit - 1)
        response = query.execute()
        
        # Populate user data for each teacher
        teachers_data = populate_teacher_user_data(
            response.data, 
            db, 
            current_user
        )
        
        return [TeacherResponse(**teacher) for teacher in teachers_data]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch teachers: {str(e)}"
        )


@router.get("/me/profile")
async def get_my_teacher_profile(
    current_user: dict = Depends(require_role(["teacher"]))
):
    """Get current teacher's profile"""
    try:
        user_id = current_user["sub"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        response = db.table("teachers").select("*").eq("user_id", user_id).single().execute()
        teacher = response.data
        
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher profile not found"
            )
        
        return TeacherResponse(**teacher)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch teacher profile: {str(e)}"
        )


@router.get("/me/classes")
async def get_my_classes(
    current_user: dict = Depends(require_role(["teacher"]))
):
    """Get classes assigned to current teacher"""
    try:
        user_id = current_user["sub"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # Get teacher ID
        teacher_response = db.table("teachers").select("id").eq("user_id", user_id).single().execute()
        teacher_id = teacher_response.data["id"]
        
        # Get assigned classes
        classes_response = db.table("classes").select("*").eq("teacher_id", teacher_id).execute()
        
        return classes_response.data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch classes: {str(e)}"
        )


@router.get("/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get teacher by ID"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        response = db.table("teachers").select("*").eq("id", teacher_id).single().execute()
        teacher = response.data
        
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found"
            )
        
        # Populate user data
        teachers_data = populate_teacher_user_data(
            [teacher], 
            db, 
            current_user
        )
        teacher = teachers_data[0] if teachers_data else teacher
        
        return TeacherResponse(**teacher)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch teacher: {str(e)}"
        )


@router.put("/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(
    teacher_id: str,
    teacher_data: TeacherUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update teacher information"""
    db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
    
    # Check permissions
    if current_user["role"] not in ["admin", "principal"]:
        # Teachers can only update their own profile
        teacher_response = db.table("teachers").select("user_id").eq("id", teacher_id).single().execute()
        if teacher_response.data["user_id"] != current_user["sub"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this teacher"
            )
    
    try:
        # Get teacher to find user_id
        teacher_response = db.table("teachers").select("*").eq("id", teacher_id).single().execute()
        teacher = teacher_response.data
        
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found"
            )
        
        # Update profile if needed
        if teacher_data.full_name or teacher_data.phone or teacher_data.address:
            profile_update = {}
            if teacher_data.full_name:
                profile_update["full_name"] = teacher_data.full_name
            if teacher_data.phone:
                profile_update["phone"] = teacher_data.phone
            if teacher_data.address:
                profile_update["address"] = teacher_data.address
            
            if profile_update:
                db.table("profiles").update(profile_update).eq("user_id", teacher["user_id"]).execute()
        
        # Update teacher record
        update_data = teacher_data.model_dump(exclude_unset=True, exclude={"full_name", "phone", "address"})
        
        if "salary_info" in update_data:
            update_data["salary_info"] = update_data["salary_info"].model_dump()
        
        if update_data:
            response = db.table("teachers").update(update_data).eq("id", teacher_id).execute()
            updated_teacher = response.data[0]
            
            # Populate user data
            teachers_data = populate_teacher_user_data(
                [updated_teacher], 
                db, 
                current_user
            )
            updated_teacher = teachers_data[0] if teachers_data else updated_teacher
            
            return TeacherResponse(**updated_teacher)
        
        # Populate user data for existing teacher
        teachers_data = populate_teacher_user_data(
            [teacher], 
            db, 
            current_user
        )
        teacher = teachers_data[0] if teachers_data else teacher
        
        return TeacherResponse(**teacher)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update teacher: {str(e)}"
        )


@router.delete("/{teacher_id}")
async def delete_teacher(
    teacher_id: str,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Deactivate teacher"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        db.table("teachers").update({"status": "inactive"}).eq("id", teacher_id).execute()
        
        return {"message": "Teacher deactivated successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to deactivate teacher: {str(e)}"
        )



