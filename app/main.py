"""Main FastAPI application"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis import redis_client
from app.core.rate_limit import RateLimitMiddleware
from app.api.routes import sites_router, pages_router, jobs_router, silos_router, onboarding_router
from app.api.routes.wordpress import router as wordpress_router
from app.queues.queue_manager import queue_manager
from app.api.exception_handlers import (
    governance_error_handler,
    validation_error_handler,
    publishing_error_handler,
    decommission_error_handler,
    cannibalization_error_handler,
    lifecycle_gate_error_handler,
    validation_exception_handler,
    integrity_error_handler,
)
from app.exceptions import (
    GovernanceError,
    ValidationError,
    PublishingError,
    DecommissionError,
    CannibalizationError,
    LifecycleGateError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    await redis_client.connect()
    await queue_manager.initialize()
    
    # Note: In production, use Alembic migrations instead
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Shutdown
    await queue_manager.close()
    await redis_client.disconnect()


app = FastAPI(
    title="Siloq - Governance-First AI SEO Platform",
    description="A governance engine for building structurally perfect websites",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - environment-aware configuration
def get_cors_origins() -> list:
    """Get CORS origins based on environment"""
    if settings.environment == "production":
        # In production, parse from comma-separated list or use specific domains
        if settings.cors_origins == "*":
            # Default production: no wildcard, require explicit origins
            return []  # Will be set via environment variable
        return [origin.strip() for origin in settings.cors_origins.split(",")]
    else:
        # Development: allow all origins
        return ["*"]


"""Get CORS methods based on environment"""
def get_cors_methods() -> list:
    if settings.cors_allow_methods == "*":
        return ["*"]
    return [method.strip() for method in settings.cors_allow_methods.split(",")]


"""Get CORS headers based on environment"""
def get_cors_headers() -> list:
    if settings.cors_allow_headers == "*":
        return ["*"]
    return [header.strip() for header in settings.cors_allow_headers.split(",")]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=get_cors_methods(),
    allow_headers=get_cors_headers(),
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Register exception handlers
app.add_exception_handler(GovernanceError, governance_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(PublishingError, publishing_error_handler)
app.add_exception_handler(DecommissionError, decommission_error_handler)
app.add_exception_handler(CannibalizationError, cannibalization_error_handler)
app.add_exception_handler(LifecycleGateError, lifecycle_gate_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)

# Include routers
app.include_router(sites_router, prefix="/api/v1")
app.include_router(pages_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(silos_router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(wordpress_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Siloq",
        "version": "0.1.0",
        "description": "Governance-First AI SEO Platform",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint with actual connection testing.
    
    Returns:
        Health status with actual connection states
    """
    from sqlalchemy import text
    from app.core.redis import redis_client
    
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }
    
    # Test database connection
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"disconnected: {str(e)}"
        health_status["status"] = "degraded"
    
    # Test Redis connection
    try:
        client = await redis_client.get_client()
        await client.ping()
        health_status["redis"] = "connected"
    except Exception as e:
        health_status["redis"] = f"disconnected: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status

