"""Validation payload contracts and schemas for decision engine."""
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# Constants
MIN_TITLE_LENGTH = 10
MIN_SLUG_LENGTH = 3


class ValidationPayload(BaseModel):
    """
    Payload for preflight validation.
    
    Attributes:
        page_id: Page identifier
        site_id: Site identifier
        path: Page path (must start with '/')
        title: Page title (minimum 10 characters)
        silo_id: Optional silo identifier
        keyword: Optional keyword
        body: Optional page body
        is_proposal: Whether this is a proposal
        metadata: Optional metadata dictionary
    """
    
    page_id: UUID
    site_id: UUID
    path: str = Field(..., min_length=1, description="Page path")
    title: str = Field(..., min_length=MIN_TITLE_LENGTH, description="Page title")
    silo_id: Optional[UUID] = None
    keyword: Optional[str] = None
    body: Optional[str] = None
    is_proposal: bool = False
    metadata: Optional[Dict] = None
    
    @validator("path")
    def validate_path_format(cls, v: str) -> str:
        """
        Validate path format.
        
        Rules:
        - Must start with '/'
        - No consecutive slashes
        - Cannot end with '/' (except root)
        """
        if not v.startswith("/"):
            raise ValueError("Path must start with '/'")
        if "//" in v:
            raise ValueError("Path cannot contain consecutive slashes")
        if v != "/" and v.endswith("/"):
            raise ValueError("Path cannot end with '/' (except root)")
        return v
    
    @validator("title")
    def validate_title_length(cls, v: str) -> str:
        """Validate title length (minimum 10 characters after trimming)."""
        trimmed = v.strip()
        if len(trimmed) < MIN_TITLE_LENGTH:
            raise ValueError(
                f"Title must be at least {MIN_TITLE_LENGTH} characters"
            )
        return trimmed
    
    class Config:
        """Pydantic configuration."""
        
        schema_extra = {
            "example": {
                "page_id": "123e4567-e89b-12d3-a456-426614174000",
                "site_id": "123e4567-e89b-12d3-a456-426614174001",
                "path": "/example-page",
                "title": "Example Page Title",
                "silo_id": "123e4567-e89b-12d3-a456-426614174002",
                "keyword": "example-keyword",
                "is_proposal": False,
            }
        }


class ErrorResponse(BaseModel):
    """
    Standardized error response.
    
    Attributes:
        code: Error code (e.g., PREFLIGHT_001)
        message: Human-readable error message
        doctrine_reference: Reference to violated policy/rule
        remediation_steps: List of steps to fix the issue
        severity: Error severity level
    """
    
    code: str
    message: str
    doctrine_reference: str
    remediation_steps: List[str]
    severity: str = "error"


class ValidationResult(BaseModel):
    """
    Result of validation with error codes.
    
    Attributes:
        passed: Whether validation passed
        errors: List of error dictionaries
        warnings: List of warning dictionaries
        state: Resulting state after validation
    """
    
    passed: bool
    errors: List[Dict[str, str]] = Field(default_factory=list)
    warnings: List[Dict[str, str]] = Field(default_factory=list)
    state: Optional[str] = None
    
    class Config:
        """Pydantic configuration."""
        
        schema_extra = {
            "example": {
                "passed": False,
                "errors": [
                    {
                        "code": "PREFLIGHT_001",
                        "message": "Page path already exists in site",
                        "doctrine_reference": "DOCTRINE-STRUCTURE-001",
                        "remediation_steps": [
                            "Check if page with same normalized path exists",
                            "Use different path or update existing page",
                        ],
                        "severity": "error",
                    }
                ],
                "warnings": [],
                "state": "draft",
            }
        }


class StateTransitionRequest(BaseModel):
    """
    Request to transition job state.
    
    Attributes:
        target_state: Target state to transition to
        reason: Optional reason for transition
        error_code: Optional error code if transition failed
    """
    
    target_state: str
    reason: Optional[str] = None
    error_code: Optional[str] = None
    
    class Config:
        """Pydantic configuration."""
        
        schema_extra = {
            "example": {
                "target_state": "preflight_approved",
                "reason": "Validation passed",
                "error_code": None,
            }
        }


class StateTransitionResponse(BaseModel):
    """
    Response from state transition.
    
    Attributes:
        success: Whether transition succeeded
        current_state: Current state after transition
        previous_state: Previous state before transition
        error: Error response if transition failed
        allowed_transitions: List of allowed transitions from current state
    """
    
    success: bool
    current_state: str
    previous_state: Optional[str] = None
    error: Optional[ErrorResponse] = None
    allowed_transitions: List[str] = Field(default_factory=list)
    
    class Config:
        """Pydantic configuration."""
        
        schema_extra = {
            "example": {
                "success": True,
                "current_state": "preflight_approved",
                "previous_state": "draft",
                "error": None,
                "allowed_transitions": ["prompt_locked", "failed"],
            }
        }
