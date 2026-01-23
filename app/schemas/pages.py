"""Pydantic schemas for Page-related requests and responses"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from app.db.models import ContentStatus


class PageCreate(BaseModel):
    """Request model for creating a new page"""
    title: str = Field(..., min_length=10, max_length=200, description="Page title (10-200 characters)")
    path: str = Field(..., description="Page path (must start with /)")
    site_id: UUID = Field(..., description="Site ID")
    silo_id: Optional[UUID] = Field(None, description="Optional silo ID")
    prompt: str = Field(..., min_length=50, description="Content generation prompt (min 50 characters)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate that path starts with /"""
        if not v.startswith('/'):
            raise ValueError('Path must start with /')
        return v.strip()


class PageResponse(BaseModel):
    """Response model for page data"""
    id: UUID
    title: str
    path: str
    status: str
    is_safe_to_publish: bool
    authority_score: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class PageUpdate(BaseModel):
    """Request model for updating a page"""
    title: Optional[str] = Field(None, min_length=10, max_length=200)
    path: Optional[str] = None
    body: Optional[str] = None
    status: Optional[ContentStatus] = None
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate that path starts with / if provided"""
        if v is not None and not v.startswith('/'):
            raise ValueError('Path must start with /')
        return v.strip() if v else None


class PublishRequest(BaseModel):
    """Request model for publishing a page"""
    force: bool = Field(False, description="Force publish even if gates fail (admin only)")


class DecommissionRequest(BaseModel):
    """Request model for decommissioning a page"""
    redirect_to: Optional[str] = Field(None, description="Redirect URL (internal path or external URL)")
    
    @field_validator('redirect_to')
    @classmethod
    def validate_redirect(cls, v: Optional[str]) -> Optional[str]:
        """Validate redirect URL format"""
        if v is None:
            return v
        # Internal path must start with /
        if v.startswith('/'):
            return v
        # External URL must have scheme
        if '://' in v:
            return v
        raise ValueError('Redirect must be an internal path (starting with /) or external URL (with scheme)')


class GateCheckResponse(BaseModel):
    """Response model for gate check results"""
    all_gates_passed: bool
    gates: Dict[str, Any]
    blocked: bool
    reason: Optional[str] = None
    failed_gates: List[str] = []

