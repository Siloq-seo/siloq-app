"""Rate limiting and production guardrails"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.redis import redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for API requests"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and root endpoint
        if request.url.path in ["/health", "/", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)
        
        # Skip if rate limiting is disabled
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # Get identifier (site_id from path or account_id from auth token)
        identifier = self._get_identifier(request)
        if not identifier:
            # If we can't identify the requester, allow but log
            return await call_next(request)
        
        # Check rate limits
        try:
            client = await redis_client.get_client()
            
            # Check per-minute limit
            minute_key = f"rate_limit:minute:{identifier}"
            minute_count = await client.get(minute_key)
            if minute_count and int(minute_count) >= settings.rate_limit_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} requests per minute"
                )
            
            # Check per-hour limit
            hour_key = f"rate_limit:hour:{identifier}"
            hour_count = await client.get(hour_key)
            if hour_count and int(hour_count) >= settings.rate_limit_per_hour:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {settings.rate_limit_per_hour} requests per hour"
                )
            
            # Check per-day limit
            day_key = f"rate_limit:day:{identifier}"
            day_count = await client.get(day_key)
            if day_count and int(day_count) >= settings.rate_limit_per_day:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {settings.rate_limit_per_day} requests per day"
                )
            
            # Increment counters
            await client.incr(minute_key)
            await client.expire(minute_key, 60)  # Expire after 1 minute
            
            await client.incr(hour_key)
            await client.expire(hour_key, 3600)  # Expire after 1 hour
            
            await client.incr(day_key)
            await client.expire(day_key, 86400)  # Expire after 1 day
            
        except HTTPException:
            raise
        except Exception:
            # If Redis is down, allow request but log error
            # In production, you might want to fail closed
            pass
        
        return await call_next(request)
    
    def _get_identifier(self, request: Request) -> Optional[str]:
        """Extract identifier for rate limiting (site_id or account_id)"""
        # Try to get site_id from path
        path_parts = request.url.path.split("/")
        if "sites" in path_parts:
            try:
                site_idx = path_parts.index("sites")
                if site_idx + 1 < len(path_parts):
                    site_id = path_parts[site_idx + 1]
                    # Validate it's a UUID
                    UUID(site_id)
                    return f"site:{site_id}"
            except (ValueError, IndexError):
                pass
        
        # Try to get account_id from auth token (if available)
        # This would require parsing the JWT token
        # For now, we'll use site_id from path as primary identifier
        
        return None


class GlobalGenerationKillSwitch:
    """Global kill switch for content generation"""
    
    @staticmethod
    async def is_generation_enabled() -> bool:
        """Check if content generation is globally enabled"""
        if not settings.global_generation_enabled:
            return False
        
        # Check Redis for runtime override
        try:
            client = await redis_client.get_client()
            override = await client.get("global:generation_enabled")
            if override is not None:
                return override.lower() == "true"
        except Exception:
            pass
        
        return True
    
    @staticmethod
    async def check_generation_allowed() -> None:
        """Raise exception if generation is disabled"""
        if not await GlobalGenerationKillSwitch.is_generation_enabled():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Content generation is currently disabled"
            )
    
    @staticmethod
    async def get_job_count(hours: int = 24) -> int:
        """Get count of jobs created in the last N hours"""
        try:
            client = await redis_client.get_client()
            # This would need to be implemented based on your job tracking
            # For now, return 0
            return 0
        except Exception:
            return 0
    
    @staticmethod
    async def check_job_limits() -> None:
        """Check if job creation limits are exceeded"""
        hour_count = await GlobalGenerationKillSwitch.get_job_count(1)
        if hour_count >= settings.max_jobs_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Maximum jobs per hour ({settings.max_jobs_per_hour}) exceeded"
            )
        
        day_count = await GlobalGenerationKillSwitch.get_job_count(24)
        if day_count >= settings.max_jobs_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Maximum jobs per day ({settings.max_jobs_per_day}) exceeded"
            )

