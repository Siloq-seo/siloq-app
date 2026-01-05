"""Pydantic schemas for Site-related requests and responses"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from uuid import UUID
from app.db.models import SiteType


class SiteCreate(BaseModel):
    """Request model for creating a new site"""
    name: str = Field(..., min_length=1, max_length=200, description="Site name")
    domain: str = Field(..., description="Site domain (e.g., example.com)")
    site_type: Optional[SiteType] = Field(None, description="Site type: LOCAL_SERVICE or ECOMMERCE")
    
    # LOCAL_SERVICE required fields
    geo_coordinates: Optional[Dict[str, Any]] = Field(None, description="Geo coordinates for LOCAL_SERVICE: {'lat': float, 'lng': float}")
    service_area: Optional[List[str]] = Field(None, description="Service areas for LOCAL_SERVICE: ['area1', 'area2', ...]")
    
    # ECOMMERCE required fields
    product_sku_pattern: Optional[str] = Field(None, description="Product SKU pattern for ECOMMERCE: e.g., 'PROD-{category}-{id}'")
    currency_settings: Optional[Dict[str, Any]] = Field(None, description="Currency settings for ECOMMERCE: {'default': 'USD', 'supported': [...]}")
    
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
    
    @validator('geo_coordinates')
    def validate_geo_coordinates(cls, v, values):
        """Validate geo_coordinates if site_type is LOCAL_SERVICE"""
        site_type = values.get('site_type')
        if site_type == SiteType.LOCAL_SERVICE:
            if not v:
                raise ValueError('geo_coordinates is required for LOCAL_SERVICE sites')
            if not isinstance(v, dict):
                raise ValueError('geo_coordinates must be a dictionary')
            if 'lat' not in v or 'lng' not in v:
                raise ValueError('geo_coordinates must contain lat and lng keys')
        return v
    
    @validator('service_area')
    def validate_service_area(cls, v, values):
        """Validate service_area if site_type is LOCAL_SERVICE"""
        site_type = values.get('site_type')
        if site_type == SiteType.LOCAL_SERVICE:
            if not v:
                raise ValueError('service_area is required for LOCAL_SERVICE sites')
            if not isinstance(v, list) or len(v) == 0:
                raise ValueError('service_area must be a non-empty list')
        return v
    
    @validator('product_sku_pattern')
    def validate_product_sku_pattern(cls, v, values):
        """Validate product_sku_pattern if site_type is ECOMMERCE"""
        site_type = values.get('site_type')
        if site_type == SiteType.ECOMMERCE:
            if not v:
                raise ValueError('product_sku_pattern is required for ECOMMERCE sites')
        return v
    
    @validator('currency_settings')
    def validate_currency_settings(cls, v, values):
        """Validate currency_settings if site_type is ECOMMERCE"""
        site_type = values.get('site_type')
        if site_type == SiteType.ECOMMERCE:
            if not v:
                raise ValueError('currency_settings is required for ECOMMERCE sites')
            if not isinstance(v, dict):
                raise ValueError('currency_settings must be a dictionary')
            if 'default' not in v:
                raise ValueError('currency_settings must contain default key')
        return v


class SiteResponse(BaseModel):
    """Response model for site data"""
    id: UUID
    name: str
    domain: str
    site_type: Optional[SiteType] = None
    geo_coordinates: Optional[Dict[str, Any]] = None
    service_area: Optional[List[str]] = None
    product_sku_pattern: Optional[str] = None
    currency_settings: Optional[Dict[str, Any]] = None
    
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

