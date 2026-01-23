"""Pydantic schemas for Site-related requests and responses"""
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
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
    
    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain format"""
        v = v.strip().lower()
        if not v:
            raise ValueError('Domain cannot be empty')
        # Basic domain validation
        if ' ' in v:
            raise ValueError('Domain cannot contain spaces')
        return v
    
    @model_validator(mode='after')
    def validate_site_type_requirements(self):
        """Validate required fields based on site_type"""
        if self.site_type == SiteType.LOCAL_SERVICE:
            if not self.geo_coordinates:
                raise ValueError('geo_coordinates is required for LOCAL_SERVICE sites')
            if not isinstance(self.geo_coordinates, dict):
                raise ValueError('geo_coordinates must be a dictionary')
            if 'lat' not in self.geo_coordinates or 'lng' not in self.geo_coordinates:
                raise ValueError('geo_coordinates must contain lat and lng keys')
            if not self.service_area:
                raise ValueError('service_area is required for LOCAL_SERVICE sites')
            if not isinstance(self.service_area, list) or len(self.service_area) == 0:
                raise ValueError('service_area must be a non-empty list')
        elif self.site_type == SiteType.ECOMMERCE:
            if not self.product_sku_pattern:
                raise ValueError('product_sku_pattern is required for ECOMMERCE sites')
            if not self.currency_settings:
                raise ValueError('currency_settings is required for ECOMMERCE sites')
            if not isinstance(self.currency_settings, dict):
                raise ValueError('currency_settings must be a dictionary')
            if 'default' not in self.currency_settings:
                raise ValueError('currency_settings must contain default key')
        return self


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
    
    model_config = ConfigDict(from_attributes=True)


class SiloCreate(BaseModel):
    """Request model for creating a new silo"""
    name: str = Field(..., min_length=1, max_length=200, description="Silo name")
    slug: str = Field(..., min_length=1, max_length=100, description="Silo slug (URL-friendly)")
    
    @field_validator('slug')
    @classmethod
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
    
    model_config = ConfigDict(from_attributes=True)

