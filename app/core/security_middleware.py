"""Security headers middleware for enhanced security."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and add security headers."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy (adjust based on your needs)
        if not settings.DEBUG:
            # Production CSP - strict
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Adjust for production
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://*.supabase.co; "
                "frame-ancestors 'none';"
            )
        else:
            # Development CSP - more permissive
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https: http:; "
                "font-src 'self' data:; "
                "connect-src 'self' http://localhost:* https://*.supabase.co; "
            )
        
        response.headers["Content-Security-Policy"] = csp
        
        # Strict Transport Security (HTTPS only)
        if not settings.DEBUG and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=()"
        )
        
        # Remove server header (hide technology stack)
        if "server" in response.headers:
            del response.headers["server"]
        
        # Remove X-Powered-By header if present
        if "x-powered-by" in response.headers:
            del response.headers["x-powered-by"]
        
        return response






