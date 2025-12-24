from supabase import create_client, Client
from app.core.config import settings
from typing import Optional

# Global client instances (lazy initialization)
_supabase_client: Optional[Client] = None
_supabase_admin_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get Supabase client instance"""
    if settings is None:
        raise RuntimeError(
            "Settings not initialized. Ensure environment variables are set before using Supabase clients."
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def get_supabase_admin_client() -> Client:
    """Get Supabase admin client with service role key"""
    if settings is None:
        raise RuntimeError(
            "Settings not initialized. Ensure environment variables are set before using Supabase clients."
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def _ensure_supabase() -> Client:
    """Lazy initialization helper for supabase client"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = get_supabase_client()
    return _supabase_client


def _ensure_supabase_admin() -> Client:
    """Lazy initialization helper for supabase admin client"""
    global _supabase_admin_client
    if _supabase_admin_client is None:
        _supabase_admin_client = get_supabase_admin_client()
    return _supabase_admin_client


# Lazy client wrapper class to support "from module import name" syntax
class _LazyClient:
    """Wrapper to provide lazy-loaded client that works with import syntax"""
    def __init__(self, getter_func):
        self._getter = getter_func
        self._client: Optional[Client] = None
    
    def _ensure_client(self) -> Client:
        if self._client is None:
            self._client = self._getter()
        return self._client
    
    def __getattr__(self, name):
        """Delegate all attribute access to the actual client"""
        return getattr(self._ensure_client(), name)
    
    def __call__(self, *args, **kwargs):
        """Allow the wrapper to be called as if it's the client"""
        return self._ensure_client()(*args, **kwargs)


# Export clients using lazy wrapper (supports "from module import name")
supabase = _LazyClient(_ensure_supabase)
supabase_admin = _LazyClient(_ensure_supabase_admin)


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
        return _ensure_supabase_admin()
    
    # For non-admin users, use Supabase session token if available (for RLS)
    # Otherwise fall back to service role for admin operations, or anon key for user operations
    if settings is None:
        raise RuntimeError(
            "Settings not initialized. Ensure environment variables are set before using Supabase clients."
        )
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


