"""Pydantic schemas for website scanning"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict


class ScanRequest(BaseModel):
    """Request to scan a website"""
    url: HttpUrl = Field(..., description="Website URL to scan")
    scan_type: str = Field(default='full', description="Scan type: 'full', 'quick', or 'technical'")
    site_id: Optional[UUID] = Field(None, description="Optional: Link scan to existing site")
    
    @field_validator('scan_type')
    @classmethod
    def validate_scan_type(cls, v):
        if v not in ['full', 'quick', 'technical']:
            raise ValueError("scan_type must be 'full', 'quick', or 'technical'")
        return v


class Recommendation(BaseModel):
    """SEO recommendation"""
    category: str
    priority: str
    issue: str
    action: str


class ScanDetails(BaseModel):
    """Detailed scan results for a category"""
    score: float
    details: Dict[str, Any]


class ScanResponse(BaseModel):
    """Scan result response"""
    id: UUID
    url: str
    domain: str
    scan_type: str
    status: str
    overall_score: Optional[float]
    grade: Optional[str]
    technical_score: Optional[float]
    content_score: Optional[float]
    structure_score: Optional[float]
    performance_score: Optional[float]
    seo_score: Optional[float]
    technical_details: Dict[str, Any]
    content_details: Dict[str, Any]
    structure_details: Dict[str, Any]
    performance_details: Dict[str, Any]
    seo_details: Dict[str, Any]
    recommendations: List[Recommendation]
    pages_crawled: int
    scan_duration_seconds: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class ScanSummary(BaseModel):
    """Summary of scan for listing"""
    id: UUID
    url: str
    domain: str
    status: str
    overall_score: Optional[float]
    grade: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


# --- Lead-gen full report (keyword cannibalization report) ---


class ScanReportSummary(BaseModel):
    """Scan summary for lead-gen report"""
    website_url: str
    total_pages_analyzed: int
    total_cannibalization_conflicts: int
    overall_risk_level: str  # Low | Medium | High


class KeywordCannibalizationItem(BaseModel):
    """Single cannibalization conflict for report"""
    keyword: str
    conflicting_urls: List[str]  # Top 2-3
    conflict_type: str  # "same intent" | "same keyword"
    severity: str  # "High" | "Medium"


class ScanReportResponse(BaseModel):
    """Full lead-gen report (no auth required to view)"""
    scan_id: UUID
    scan_summary: ScanReportSummary
    keyword_cannibalization_details: List[KeywordCannibalizationItem]
    educational_explanation: Dict[str, str]  # title, body
    locked_recommendations: List[str]  # Teaser titles only
    upgrade_cta: Dict[str, str]  # label, url (with scan_id appended by backend or frontend)
