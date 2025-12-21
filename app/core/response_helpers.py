"""Helper functions for populating response data with user information"""
from typing import List, Dict, Any, Optional
from app.core.supabase import get_request_scoped_client
from app.models.user import UserResponse


def populate_student_user_data(
    students: List[Dict[str, Any]], 
    db_client,
    current_user: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Populate student records with user data from profiles table"""
    if not students:
        return students
    
    # Get all user_ids
    user_ids = [s.get("user_id") for s in students if s.get("user_id")]
    if not user_ids:
        return students
    
    # Fetch all profiles in one query
    try:
        profiles_response = db_client.table("profiles").select("user_id, full_name, phone, address, avatar_url, created_at").in_("user_id", user_ids).execute()
        profiles_map = {
            p.get("user_id"): p 
            for p in profiles_response.data
        }
        
        # Get auth user emails (if admin/principal)
        emails_map = {}
        if current_user.get("role") in ["admin", "principal"]:
            try:
                from app.core.supabase import supabase_admin
                for user_id in user_ids:
                    try:
                        auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
                        if auth_user and auth_user.user:
                            emails_map[user_id] = auth_user.user.email
                    except Exception:
                        pass  # Skip if can't get email
            except Exception:
                pass  # Skip email fetching if not available
        
        # Attach user data to each student
        for student in students:
            user_id = student.get("user_id")
            if user_id and user_id in profiles_map:
                profile = profiles_map[user_id]
                student["user"] = {
                    "id": user_id,
                    "email": emails_map.get(user_id, ""),
                    "full_name": profile.get("full_name", ""),
                    "role": "student",
                    "phone": profile.get("phone"),
                    "address": profile.get("address"),
                    "avatar_url": profile.get("avatar_url"),
                    "created_at": profile.get("created_at")
                }
    except Exception:
        # If profile fetch fails, continue without user data
        pass
    
    return students


def populate_teacher_user_data(
    teachers: List[Dict[str, Any]], 
    db_client,
    current_user: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Populate teacher records with user data from profiles table"""
    if not teachers:
        return teachers
    
    # Get all user_ids
    user_ids = [t.get("user_id") for t in teachers if t.get("user_id")]
    if not user_ids:
        return teachers
    
    # Fetch all profiles in one query
    try:
        profiles_response = db_client.table("profiles").select("user_id, full_name, phone, address, avatar_url, created_at").in_("user_id", user_ids).execute()
        profiles_map = {
            p.get("user_id"): p 
            for p in profiles_response.data
        }
        
        # Get auth user emails (if admin/principal)
        emails_map = {}
        if current_user.get("role") in ["admin", "principal"]:
            try:
                from app.core.supabase import supabase_admin
                for user_id in user_ids:
                    try:
                        auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
                        if auth_user and auth_user.user:
                            emails_map[user_id] = auth_user.user.email
                    except Exception:
                        pass  # Skip if can't get email
            except Exception:
                pass  # Skip email fetching if not available
        
        # Attach user data to each teacher
        for teacher in teachers:
            user_id = teacher.get("user_id")
            if user_id and user_id in profiles_map:
                profile = profiles_map[user_id]
                teacher["user"] = {
                    "id": user_id,
                    "email": emails_map.get(user_id, ""),
                    "full_name": profile.get("full_name", ""),
                    "role": "teacher",
                    "phone": profile.get("phone"),
                    "address": profile.get("address"),
                    "avatar_url": profile.get("avatar_url"),
                    "created_at": profile.get("created_at")
                }
    except Exception:
        # If profile fetch fails, continue without user data
        pass
    
    return teachers

