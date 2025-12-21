from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings, validate_settings
from app.core.logging_config import setup_logging, get_logger
from app.core.exceptions import (
    SchoolManagementException,
    ConfigurationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    sanitize_error_message
)
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_middleware import SecurityHeadersMiddleware
from app.api.v1.router import api_router

# Setup logging first (before settings validation)
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        validate_settings()
        logger.info(f"✅ Configuration validated successfully")
        
        logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info(f"Debug mode: {'ON' if settings.DEBUG else 'OFF'}")
        logger.info(f"Frontend URL: {settings.FRONTEND_URL}")
    except ConfigurationError as e:
        logger.error(f"❌ Configuration error: {e.message}")
        logger.error("Application startup failed due to configuration issues.")
        raise
    except Exception as e:
        logger.exception("❌ Unexpected error during startup")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


# Initialize FastAPI app
# Disable docs in production for security
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Comprehensive School Management System API",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)

# Global exception handler for custom exceptions
@app.exception_handler(SchoolManagementException)
async def custom_exception_handler(request: Request, exc: SchoolManagementException):
    """Handle custom application exceptions."""
    logger.error(
        f"Application error: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "details": exc.details,
            "path": str(request.url),
            "method": request.method,
        }
    )
    
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, (AuthenticationError, AuthorizationError)):
        status_code = status.HTTP_401_UNAUTHORIZED if isinstance(exc, AuthenticationError) else status.HTTP_403_FORBIDDEN
    elif isinstance(exc, NotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, ConfigurationError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": True,
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details if settings.DEBUG else None,
        }
    )


# Global exception handler for all other exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}",
        extra={
            "path": str(request.url),
            "method": request.method,
        }
    )
    
    sanitized_message = sanitize_error_message(exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": sanitized_message,
            "error_code": "INTERNAL_ERROR",
            "details": {
                "type": type(exc).__name__,
                "message": str(exc),
            } if settings.DEBUG else None,
        }
    )


# Security headers middleware (add first to ensure headers are set)
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting middleware (before CORS)
# In production, consider using Redis-based rate limiting for multiple workers
if not settings.DEBUG:
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_size=10
    )

# CORS Configuration
# Get allowed origins from environment or use defaults
allowed_origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Remove duplicates while preserving order
seen = set()
allowed_origins = [x for x in allowed_origins if not (x in seen or seen.add(x))]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if not settings.DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit-PerMinute", "X-RateLimit-Limit-PerHour"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
    }


@app.get("/health")
async def health_check():
    """Enhanced health check endpoint for production monitoring."""
    from app.core.supabase import supabase_admin
    
    health_status = {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
    
    # Check database connectivity
    try:
        # Simple query to verify database connection
        response = supabase_admin.table("profiles").select("count", count="exact").limit(1).execute()
        health_status["database"] = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_status["database"] = "disconnected"
        health_status["status"] = "degraded"
    
    # Determine overall status code
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(content=health_status, status_code=status_code)


