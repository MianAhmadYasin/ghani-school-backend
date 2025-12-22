"""Logging configuration for the School Management System."""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from app.core.config import settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Setup application-wide logging configuration.
    
    Args:
        log_level: Optional log level override. If None, uses DEBUG if settings.DEBUG else INFO
    """
    # Determine log level
    if log_level:
        level = getattr(logging, log_level.upper(), logging.INFO)
    else:
        level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    # Create logs directory if it doesn't exist
    # In Docker/production, logs go to stdout/stderr, so file logging is optional
    log_dir = Path("logs")
    try:
        log_dir.mkdir(exist_ok=True)
    except (PermissionError, OSError):
        # If we can't create logs directory (e.g., in some Docker setups), skip file logging
        log_dir = None
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler (always use simple format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation (detailed format) - only if log directory is writable
    if log_dir:
        try:
            file_handler = RotatingFileHandler(
                filename=log_dir / "app.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            root_logger.addHandler(file_handler)
            
            # Error file handler (only errors and above)
            error_handler = RotatingFileHandler(
                filename=log_dir / "errors.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(detailed_formatter)
            root_logger.addHandler(error_handler)
        except (PermissionError, OSError):
            # If file logging fails, continue with console logging only
            root_logger.warning("File logging not available, using console logging only")
    
    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    root_logger.info(f"Logging initialized at {level} level")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)








