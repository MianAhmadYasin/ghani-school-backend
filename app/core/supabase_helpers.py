"""Helper functions for Supabase client management"""

from app.core.supabase import get_request_scoped_client, Client
from typing import Dict, Any, Optional


def get_db_client(current_user: Dict[str, Any], is_admin_operation: bool = False) -> Client:
    """Helper function to get properly scoped Supabase client from current_user.
    
    This is the recommended way to get a Supabase client that respects RLS policies.
    It automatically extracts the Supabase token from the JWT payload if available.
    
    Args:
        current_user: User dict from get_current_user dependency (contains access_token and supabase_token)
        is_admin_operation: Whether this operation requires admin privileges (uses service role)
        
    Returns:
        Supabase client configured for the request with proper RLS support
    """
    access_token = current_user.get("access_token")
    supabase_token = current_user.get("supabase_token")
    is_admin = current_user.get("role") in ["admin", "principal"] or is_admin_operation
    
    return get_request_scoped_client(access_token, is_admin, supabase_token)

