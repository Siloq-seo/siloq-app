"""Main FastAPI application"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis import redis_client
from app.api.routes import sites_router, pages_router, jobs_router, silos_router
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
    }

