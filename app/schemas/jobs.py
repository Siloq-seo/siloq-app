"""Pydantic schemas for Job-related requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class JobResponse(BaseModel):
    """Response model for job data"""
    id: UUID
    page_id: UUID
    status: str
    retry_count: int
    max_retries: int
    total_cost_usd: float
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    """Response model for job status"""
    job_id: str
    status: str
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Progress from 0.0 to 1.0")
    metadata: Optional[Dict[str, Any]] = None

