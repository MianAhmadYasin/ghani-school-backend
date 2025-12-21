from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field
from typing import List
import re
from urllib.parse import urlparse


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "School Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode (set to false in production)")
    ENVIRONMENT: str = Field(default="production", description="Environment: development, staging, production")
    
    # Supabase
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_KEY: str = Field(..., description="Supabase anon key")
    SUPABASE_SERVICE_KEY: str = Field(..., description="Supabase service role key")
    
    # JWT
    JWT_SECRET_KEY: str = Field(..., min_length=32, description="JWT secret key (minimum 32 characters)")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Server
    PORT: int = Field(default=8000, description="Server port (Railway sets this automatically)")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
    
    @field_validator('SUPABASE_URL')
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Validate Supabase URL format."""
        if not v:
            raise ValueError("SUPABASE_URL is required")
        try:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("SUPABASE_URL must be a valid URL (e.g., https://xxxxx.supabase.co)")
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("SUPABASE_URL must use http or https protocol")
        except Exception as e:
            raise ValueError(f"Invalid SUPABASE_URL format: {e}")
        return v
    
    @field_validator('SUPABASE_KEY')
    @classmethod
    def validate_supabase_key(cls, v: str) -> str:
        """Validate Supabase key is not empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("SUPABASE_KEY is required and cannot be empty")
        return v
    
    @field_validator('SUPABASE_SERVICE_KEY')
    @classmethod
    def validate_supabase_service_key(cls, v: str) -> str:
        """Validate Supabase service key is not empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("SUPABASE_SERVICE_KEY is required and cannot be empty")
        return v
    
    @field_validator('JWT_SECRET_KEY')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret key strength."""
        if not v or len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters long. "
                "Generate one using: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v
    
    @field_validator('FRONTEND_URL')
    @classmethod
    def validate_frontend_url(cls, v: str) -> str:
        """Validate frontend URL format."""
        if v:
            try:
                parsed = urlparse(v)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError("FRONTEND_URL must be a valid URL")
            except Exception as e:
                raise ValueError(f"Invalid FRONTEND_URL format: {e}")
        return v


def validate_settings() -> None:
    """Validate all required settings are present and valid."""
    from app.core.exceptions import ConfigurationError
    
    try:
        # Re-initialize settings to ensure validation
        global settings
        settings = Settings()
        
        # Additional validations
        if not settings.SUPABASE_URL.startswith('https://') and not settings.DEBUG:
            raise ConfigurationError(
                "SUPABASE_URL should use HTTPS in production",
                error_code="INSECURE_URL"
            )
    except Exception as e:
        error_msg = str(e)
        if "required" in error_msg.lower() or "field required" in error_msg.lower():
            missing_field = ""
            for field in ['SUPABASE_URL', 'SUPABASE_KEY', 'SUPABASE_SERVICE_KEY', 'JWT_SECRET_KEY']:
                if field.lower() in error_msg.lower():
                    missing_field = field
                    break
            
            raise ConfigurationError(
                f"Missing required environment variable: {missing_field or 'See error details'}\n"
                f"Please check your .env file and ensure all required variables are set.\n"
                f"Error: {error_msg}",
                error_code="MISSING_ENV_VAR"
            )
        else:
            raise ConfigurationError(
                f"Configuration error: {error_msg}\n"
                f"Please check your .env file configuration.",
                error_code="CONFIG_ERROR"
            )


# Initialize settings and validate
try:
    settings = Settings()
except Exception as e:
    # Settings will be validated in main.py startup
    settings = None


