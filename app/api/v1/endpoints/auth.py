from fastapi import APIRouter, HTTPException, status, Depends
from app.models.user import UserLogin, TokenResponse, UserCreate, UserResponse, PasswordChange
from app.core.supabase import supabase, supabase_admin
from app.core.security import create_access_token, get_current_user, verify_password, get_password_hash
from app.core.logging_config import get_logger
from app.core.exceptions import (
    AuthenticationError,
    DatabaseError,
    ValidationError,
    sanitize_error_message
)
from datetime import timedelta
from app.core.config import settings

logger = get_logger(__name__)
router = APIRouter()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate):
    """Register a new user (admin only in production)"""
    try:
        # Create auth user in Supabase
        auth_response = supabase_admin.auth.admin.create_user({
            "email": user_data.email,
            "password": user_data.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": user_data.full_name,
                "role": user_data.role.value
            }
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
        
        user_id = auth_response.user.id
        
        # Create profile in profiles table
        profile_data = {
            "user_id": user_id,
            "full_name": user_data.full_name,
            "phone": user_data.phone,
            "address": user_data.address,
        }
        
        profile_response = supabase.table("profiles").insert(profile_data).execute()
        
        # Return user response
        logger.info(f"User created successfully: {user_id} ({user_data.email})")
        return UserResponse(
            id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            phone=user_data.phone,
            address=user_data.address,
            created_at=auth_response.user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create user {user_data.email}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create user: {error_message}", error_code="USER_CREATE_ERROR")


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with email and password"""
    try:
        # Sign in with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user = auth_response.user
        session = auth_response.session
        
        if not session or not session.access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to create session"
            )
        
        # Get user profile
        profile_response = supabase.table("profiles").select("*").eq("user_id", user.id).single().execute()
        profile = profile_response.data if profile_response.data else {}
        
        # Get role from user metadata
        role = user.user_metadata.get("role", "student")
        
        # Create custom JWT token that includes Supabase session info
        # This token is used by our FastAPI backend for authorization
        # The Supabase session token should be used for direct Supabase calls
        access_token = create_access_token(
            data={
                "sub": user.id,
                "email": user.email,
                "role": role,
                "supabase_token": session.access_token  # Include Supabase token for RLS
            }
        )
        
        user_response = UserResponse(
            id=user.id,
            email=user.email,
            full_name=profile.get("full_name", ""),
            role=role,
            phone=profile.get("phone"),
            address=profile.get("address"),
            avatar_url=profile.get("avatar_url"),
            created_at=user.created_at
        )
        
        logger.info(f"User logged in successfully: {user.email} ({role})")
        return TokenResponse(
            access_token=access_token,
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Login failed for {credentials.email}: {str(e)}")
        error_message = sanitize_error_message(e)
        # For login errors, return HTTPException to maintain API compatibility
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_message
        )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout current user"""
    try:
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logout failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    try:
        user_id = current_user["sub"]
        
        # Get profile
        profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).single().execute()
        profile = profile_response.data
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        return UserResponse(
            id=user_id,
            email=current_user["email"],
            full_name=profile.get("full_name", ""),
            role=current_user["role"],
            phone=profile.get("phone"),
            address=profile.get("address"),
            avatar_url=profile.get("avatar_url"),
            created_at=profile.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch user profile: {str(e)}"
        )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    try:
        # Update password in Supabase
        supabase.auth.update_user({
            "password": password_data.new_password
        })
        
        return {"message": "Password changed successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to change password: {str(e)}"
        )












