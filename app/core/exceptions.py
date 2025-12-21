"""Custom exception classes for the School Management System."""
from typing import Optional, Dict, Any


class SchoolManagementException(Exception):
    """Base exception for all application-specific exceptions."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(SchoolManagementException):
    """Exception raised for database-related errors."""
    pass


class ValidationError(SchoolManagementException):
    """Exception raised for validation errors."""
    pass


class AuthenticationError(SchoolManagementException):
    """Exception raised for authentication errors."""
    pass


class AuthorizationError(SchoolManagementException):
    """Exception raised for authorization errors."""
    pass


class NotFoundError(SchoolManagementException):
    """Exception raised when a resource is not found."""
    pass


class ConflictError(SchoolManagementException):
    """Exception raised for resource conflicts (e.g., duplicate entries)."""
    pass


class ConfigurationError(SchoolManagementException):
    """Exception raised for configuration errors."""
    pass


def sanitize_error_message(error: Exception, include_details: bool = False) -> str:
    """
    Sanitize error messages to prevent leaking sensitive information.
    
    Args:
        error: The exception to sanitize
        include_details: Whether to include detailed error information (dev only)
        
    Returns:
        Sanitized error message
    """
    from app.core.config import settings
    
    # If it's our custom exception, use its message
    if isinstance(error, SchoolManagementException):
        return error.message
    
    # For known exception types, provide user-friendly messages
    error_type = type(error).__name__
    error_str = str(error)
    
    # List of potentially sensitive patterns (case-insensitive)
    sensitive_patterns = [
        'password',
        'secret',
        'key',
        'token',
        'credential',
        'auth',
        'connection',
        'database',
        'sql',
        'query',
    ]
    
    # Check if error message contains sensitive information
    error_lower = error_str.lower()
    is_sensitive = any(pattern in error_lower for pattern in sensitive_patterns)
    
    if is_sensitive and not settings.DEBUG:
        # In production, return generic message for sensitive errors
        if 'password' in error_lower or 'credential' in error_lower:
            return "Authentication failed. Please check your credentials."
        elif 'connection' in error_lower or 'database' in error_lower:
            return "Database connection error. Please try again later."
        elif 'token' in error_lower or 'auth' in error_lower:
            return "Authentication error. Please login again."
        else:
            return "An error occurred. Please try again or contact support."
    
    # In debug mode or for non-sensitive errors, return the actual message
    if settings.DEBUG or include_details:
        return f"{error_type}: {error_str}"
    else:
        return "An error occurred. Please try again."








