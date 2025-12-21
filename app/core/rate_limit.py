"""Rate limiting middleware for API protection."""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
import time
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.
    For production with multiple workers, consider using Redis-based rate limiting.
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        
        # Store request timestamps per IP
        # Format: {ip: [(timestamp, count), ...]}
        self.request_history: Dict[str, list] = defaultdict(list)
        
        # Cleanup interval (clean old entries every 5 minutes)
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (for reverse proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _cleanup_old_entries(self):
        """Remove old entries to prevent memory leaks."""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        cutoff_time = current_time - 3600  # 1 hour ago
        
        # Clean up old entries
        ips_to_remove = []
        for ip, timestamps in self.request_history.items():
            # Keep only recent entries (within last hour)
            self.request_history[ip] = [
                ts for ts in timestamps if ts[0] > cutoff_time
            ]
            
            # Remove IP if no entries left
            if not self.request_history[ip]:
                ips_to_remove.append(ip)
        
        for ip in ips_to_remove:
            del self.request_history[ip]
        
        self.last_cleanup = current_time
    
    def _check_rate_limit(self, ip: str, current_time: float) -> Tuple[bool, str]:
        """
        Check if request should be allowed based on rate limits.
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Cleanup old entries periodically
        self._cleanup_old_entries()
        
        # Get request history for this IP
        history = self.request_history[ip]
        
        # Remove entries older than 1 hour
        hour_ago = current_time - 3600
        history = [ts for ts in history if ts[0] > hour_ago]
        
        # Count requests in last minute
        minute_ago = current_time - 60
        requests_last_minute = sum(1 for ts, _ in history if ts > minute_ago)
        
        # Count requests in last hour
        requests_last_hour = len(history)
        
        # Check burst limit (requests in last second)
        second_ago = current_time - 1
        requests_last_second = sum(1 for ts, _ in history if ts > second_ago)
        
        # Check limits
        if requests_last_second >= self.burst_size:
            return False, f"Burst limit exceeded: {self.burst_size} requests/second"
        
        if requests_last_minute >= self.requests_per_minute:
            return False, f"Rate limit exceeded: {self.requests_per_minute} requests/minute"
        
        if requests_last_hour >= self.requests_per_hour:
            return False, f"Rate limit exceeded: {self.requests_per_hour} requests/hour"
        
        # Add current request to history
        history.append((current_time, 1))
        self.request_history[ip] = history
        
        return True, "OK"
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/api/docs", "/api/redoc", "/api/openapi.json"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check rate limit
        current_time = time.time()
        allowed, reason = self._check_rate_limit(client_ip, current_time)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for IP {client_ip}: {reason}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": True,
                    "message": "Rate limit exceeded",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "details": reason,
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit-PerMinute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Limit-PerHour"] = str(self.requests_per_hour)
        
        return response






