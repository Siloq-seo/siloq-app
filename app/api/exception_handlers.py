"""Exception handlers for FastAPI application"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from app.exceptions import (
    GovernanceError,
    ValidationError,
    PublishingError,
    DecommissionError,
    CannibalizationError,
    LifecycleGateError,
)


async def governance_error_handler(request: Request, exc: GovernanceError) -> JSONResponse:
    """Handle governance-related errors"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.to_dict(),
            "path": str(request.url.path),
        },
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": exc.to_dict(),
            "path": str(request.url.path),
        },
    )


async def publishing_error_handler(request: Request, exc: PublishingError) -> JSONResponse:
    """Handle publishing errors"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.to_dict(),
            "path": str(request.url.path),
        },
    )


async def decommission_error_handler(request: Request, exc: DecommissionError) -> JSONResponse:
    """Handle decommission errors"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.to_dict(),
            "path": str(request.url.path),
        },
    )


async def cannibalization_error_handler(request: Request, exc: CannibalizationError) -> JSONResponse:
    """Handle cannibalization errors"""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,  # Conflict because content would cannibalize
        content={
            "error": exc.to_dict(),
            "path": str(request.url.path),
        },
    )


async def lifecycle_gate_error_handler(request: Request, exc: LifecycleGateError) -> JSONResponse:
    """Handle lifecycle gate errors"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.to_dict(),
            "path": str(request.url.path),
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
            "path": str(request.url.path),
        },
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle database integrity errors (e.g., unique constraint violations)"""
    error_message = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
    
    # Check for common constraint violations
    if "unique" in error_message.lower() or "duplicate" in error_message.lower():
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "UNIQUE_CONSTRAINT_VIOLATION",
                    "message": "A record with this value already exists",
                    "details": error_message,
                },
                "path": str(request.url.path),
            },
        )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "Database constraint violation",
                "details": error_message,
            },
            "path": str(request.url.path),
        },
    )

