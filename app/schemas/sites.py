"""Pydantic schemas for Site-related requests and responses"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from uuid import UUID


class SiteCreate(BaseModel):
    """Request model for creating a new site"""
    name: str = Field(..., min_length=1, max_length=200, description="Site name")
    domain: str = Field(..., description="Site domain (e.g., example.com)")
    
    @validator('domain')
    def validate_domain(cls, v: str) -> str:
        """Validate domain format"""
        v = v.strip().lower()
        if not v:
            raise ValueError('Domain cannot be empty')
        # Basic domain validation
        if ' ' in v:
            raise ValueError('Domain cannot contain spaces')
        return v


class SiteResponse(BaseModel):
    """Response model for site data"""
    id: UUID
    name: str
    domain: str
    
    class Config:
        from_attributes = True


class SiloCreate(BaseModel):
    """Request model for creating a new silo"""
    name: str = Field(..., min_length=1, max_length=200, description="Silo name")
    slug: str = Field(..., min_length=1, max_length=100, description="Silo slug (URL-friendly)")
    
    @validator('slug')
    def validate_slug(cls, v: str) -> str:
        """Validate slug format"""
        v = v.strip().lower()
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Slug must contain only alphanumeric characters, hyphens, and underscores')
        return v


class SiloResponse(BaseModel):
    """Response model for silo data"""
    id: UUID
    name: str
    slug: str
    site_id: UUID
    position: Optional[int] = None
    
    class Config:
        from_attributes = True

