from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from app.models.user import UserResponse, UserUpdate
from app.core.supabase import supabase, supabase_admin
from app.core.security import get_current_user, require_role
from app.core.logging_config import get_logger
from app.core.exceptions import DatabaseError, NotFoundError, sanitize_error_message

logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=list[UserResponse])
async def list_users(
    role: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """List all users with optional filters"""
    try:
        # Admin endpoints always use service role to bypass RLS
        query = supabase_admin.table("profiles").select("*, user_id")
        
        if search:
            query = query.ilike("full_name", f"%{search}%")
        
        query = query.range(offset, offset + limit - 1)
        response = query.execute()
        
        users = []
        for profile in response.data:
            # Get user auth data
            try:
                user_data = supabase_admin.auth.admin.get_user_by_id(profile["user_id"])
                user_role = user_data.user.user_metadata.get("role", "student")
                
                if role and user_role != role:
                    continue
                
                users.append(UserResponse(
                    id=profile["user_id"],
                    email=user_data.user.email,
                    full_name=profile.get("full_name", ""),
                    role=user_role,
                    phone=profile.get("phone"),
                    address=profile.get("address"),
                    avatar_url=profile.get("avatar_url"),
                    created_at=profile.get("created_at")
                ))
            except (KeyError, AttributeError, TypeError) as e:
                # Skip users with missing or invalid data
                logger.warning(f"Skipping user {profile.get('user_id', 'unknown')}: {str(e)}")
                continue
            except Exception as e:
                # Log unexpected errors but continue processing other users
                logger.error(f"Error fetching user {profile.get('user_id', 'unknown')}: {str(e)}")
                continue
        
        return users
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch users: {str(e)}")
        error_message = sanitize_error_message(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch users: {error_message}"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Get user by ID"""
    try:
        # Get profile
        profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).single().execute()
        profile = profile_response.data
        
        if not profile:
            raise NotFoundError(f"User with ID {user_id} not found", error_code="USER_NOT_FOUND")
        
        # Get auth data
        user_data = supabase_admin.auth.admin.get_user_by_id(user_id)
        
        return UserResponse(
            id=user_id,
            email=user_data.user.email,
            full_name=profile.get("full_name", ""),
            role=user_data.user.user_metadata.get("role", "student"),
            phone=profile.get("phone"),
            address=profile.get("address"),
            avatar_url=profile.get("avatar_url"),
            created_at=profile.get("created_at")
        )
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except (KeyError, AttributeError) as e:
        logger.error(f"Data structure error fetching user {user_id}: {str(e)}")
        raise DatabaseError(f"Invalid user data structure", error_code="INVALID_DATA")
    except Exception as e:
        logger.error(f"Failed to fetch user {user_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch user: {error_message}", error_code="FETCH_ERROR")


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile"""
    from app.core.exceptions import AuthorizationError
    
    # Check permissions: users can update themselves, admins can update anyone
    if current_user["sub"] != user_id and current_user["role"] not in ["admin", "principal"]:
        raise AuthorizationError(
            "Not authorized to update this user",
            error_code="UNAUTHORIZED_UPDATE"
        )
    
    try:
        # Update profile
        update_data = user_data.model_dump(exclude_unset=True)
        
        if update_data:
            supabase.table("profiles").update(update_data).eq("user_id", user_id).execute()
        
        # Get updated profile
        profile_response = supabase.table("profiles").select("*").eq("user_id", user_id).single().execute()
        profile = profile_response.data
        
        if not profile:
            raise NotFoundError(f"User with ID {user_id} not found", error_code="USER_NOT_FOUND")
        
        # Get auth data
        user_auth = supabase_admin.auth.admin.get_user_by_id(user_id)
        
        return UserResponse(
            id=user_id,
            email=user_auth.user.email,
            full_name=profile.get("full_name", ""),
            role=user_auth.user.user_metadata.get("role", "student"),
            phone=profile.get("phone"),
            address=profile.get("address"),
            avatar_url=profile.get("avatar_url"),
            created_at=profile.get("created_at")
        )
        
    except (NotFoundError, AuthorizationError):
        raise
    except (KeyError, AttributeError) as e:
        logger.error(f"Data structure error updating user {user_id}: {str(e)}")
        raise DatabaseError(f"Invalid user data structure", error_code="INVALID_DATA")
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update user: {error_message}", error_code="UPDATE_ERROR")


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Deactivate user (soft delete)"""
    try:
        # Delete user from Supabase Auth
        supabase_admin.auth.admin.delete_user(user_id)
        
        logger.info(f"User {user_id} deleted by admin {current_user.get('sub')}")
        return {"message": "User deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to delete user: {error_message}", error_code="DELETE_ERROR")












