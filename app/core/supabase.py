from supabase import create_client, Client
from app.core.config import settings


def get_supabase_client() -> Client:
    """Get Supabase client instance"""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def get_supabase_admin_client() -> Client:
    """Get Supabase admin client with service role key"""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


# Global client instances
supabase: Client = get_supabase_client()
supabase_admin: Client = get_supabase_admin_client()


def get_request_scoped_client(access_token: str | None, is_admin: bool, supabase_token: str | None = None) -> Client:
    """Return a Supabase client suited for the current request.
    - Admins use the service role client (bypass RLS).
    - Non-admins use a user client with the Supabase JWT token (enforces RLS).
    
    Args:
        access_token: Custom JWT token from our backend
        is_admin: Whether user is admin/principal (uses service role)
        supabase_token: Supabase session token for RLS (extracted from JWT payload)
    """
    if is_admin:
        return supabase_admin
    
    # For non-admin users, use Supabase session token if available (for RLS)
    # Otherwise fall back to service role for admin operations, or anon key for user operations
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    
    # If we have a Supabase session token, use it for RLS
    # Supabase RLS requires Supabase's own JWT format
    if supabase_token:
        # Set Supabase JWT token in PostgREST headers for RLS
        # This is the correct way to enable RLS with Supabase Python client
        client.postgrest.headers.update({"Authorization": f"Bearer {supabase_token}"})
    elif access_token:
        # Fallback: set custom JWT in headers (for backend auth, but RLS may not work fully)
        # This is used when Supabase token is not available (e.g., old tokens)
        client.postgrest.headers.update({"Authorization": f"Bearer {access_token}"})
    
    return client


