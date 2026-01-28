"""Content jobs management routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import Optional, List

from app.core.database import get_db
from app.core.auth import get_current_user
from app.db.models import GenerationJob, Page, Site

router = APIRouter(prefix="/content-jobs", tags=["content-jobs"])


@router.get("")
async def list_content_jobs(
    status: Optional[str] = Query(None, description="Filter by job status"),
    siteId: Optional[UUID] = Query(None, alias="siteId", description="Filter by site ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all content generation jobs with optional filters.
    
    Args:
        status: Filter by job status
        siteId: Filter by site ID
        db: Database session
        
    Returns:
        List of content jobs
    """
    query = select(GenerationJob).join(Page).join(Site)
    
    # Apply filters
    if status:
        query = query.where(GenerationJob.status == status)
    if siteId:
        query = query.where(Site.id == siteId)
    
    # Order by created_at descending
    query = query.order_by(GenerationJob.created_at.desc())
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Format response to match dashboard expectations
    jobs_list = []
    for job in jobs:
        page = await db.get(Page, job.page_id)
        site = await db.get(Site, page.site_id) if page else None
        
        # Map status to dashboard format
        status_map = {
            "draft": "PREFLIGHT_APPROVED",
            "preflight_approved": "PREFLIGHT_APPROVED",
            "prompt_locked": "PROMPT_LOCKED",
            "processing": "GENERATING",
            "postcheck_passed": "POSTCHECK_PASSED",
            "postcheck_failed": "POSTCHECK_FAILED",
            "completed": "COMPLETE",
            "failed": "FAILED",
            "ai_max_retry_exceeded": "FAILED",
        }
        
        jobs_list.append({
            "id": str(job.id),
            "pageId": str(job.page_id),
            "pageTitle": page.title if page else "Unknown",
            "siteId": str(page.site_id) if page else None,
            "status": status_map.get(job.status, job.status.upper()),
            "createdAt": job.created_at.isoformat() if job.created_at else None,
            "updatedAt": job.completed_at.isoformat() if job.completed_at else (job.created_at.isoformat() if job.created_at else None),
            "costEstimate": job.total_cost_usd,
            "retries": job.retry_count,
            "error": job.error_message,
            "validationResults": {
                "preflight": page.governance_checks.get("preflight") if page and page.governance_checks else None,
                "postcheck": page.governance_checks.get("postcheck") if page and page.governance_checks else None,
            } if page and page.governance_checks else None,
        })
    
    return jobs_list


@router.get("/{job_id}")
async def get_content_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific content generation job by ID.
    
    Args:
        job_id: Job UUID
        db: Database session
        
    Returns:
        Content job details
        
    Raises:
        HTTPException: 404 if job not found
    """
    job = await db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Content job not found")
    
    page = await db.get(Page, job.page_id)
    site = await db.get(Site, page.site_id) if page else None
    
    # Map status to dashboard format
    status_map = {
        "draft": "PREFLIGHT_APPROVED",
        "preflight_approved": "PREFLIGHT_APPROVED",
        "prompt_locked": "PROMPT_LOCKED",
        "processing": "GENERATING",
        "postcheck_passed": "POSTCHECK_PASSED",
        "postcheck_failed": "POSTCHECK_FAILED",
        "completed": "COMPLETE",
        "failed": "FAILED",
        "ai_max_retry_exceeded": "FAILED",
    }
    
    return {
        "id": str(job.id),
        "pageId": str(job.page_id),
        "pageTitle": page.title if page else "Unknown",
        "siteId": str(page.site_id) if page else None,
        "status": status_map.get(job.status, job.status.upper()),
        "createdAt": job.created_at.isoformat() if job.created_at else None,
        "updatedAt": job.completed_at.isoformat() if job.completed_at else (job.created_at.isoformat() if job.created_at else None),
        "costEstimate": job.total_cost_usd,
        "retries": job.retry_count,
        "error": job.error_message,
        "validationResults": {
            "preflight": page.governance_checks.get("preflight") if page and page.governance_checks else None,
            "postcheck": page.governance_checks.get("postcheck") if page and page.governance_checks else None,
        } if page and page.governance_checks else None,
    }


@router.post("")
async def create_content_job(
    job_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new content generation job.
    
    Args:
        job_data: Job creation data (pageId, siteId)
        db: Database session
        
    Returns:
        Created job with ID
        
    Raises:
        HTTPException: 404 if page not found, 400 if invalid data
    """
    page_id = job_data.get("pageId")
    site_id = job_data.get("siteId")
    
    if not page_id:
        raise HTTPException(status_code=400, detail="pageId is required")
    
    try:
        page_uuid = UUID(page_id) if isinstance(page_id, str) else page_id
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pageId format")
    
    # Verify page exists
    page = await db.get(Page, page_uuid)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Verify site matches if provided
    if site_id:
        try:
            site_uuid = UUID(site_id) if isinstance(site_id, str) else site_id
            if page.site_id != site_uuid:
                raise HTTPException(status_code=400, detail="Page does not belong to specified site")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid siteId format")
    
    # Create generation job
    # Note: In a full implementation, this would queue the job via queue_manager
    # For now, we'll create a draft job record
    from datetime import datetime
    import uuid
    
    job = GenerationJob(
        id=uuid.uuid4(),
        page_id=page_uuid,
        job_id=f"job_{uuid.uuid4()}",
        status="draft",
        retry_count=0,
        max_retries=3,
        total_cost_usd=0.0,
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Map status to dashboard format
    status_map = {
        "draft": "PREFLIGHT_APPROVED",
        "preflight_approved": "PREFLIGHT_APPROVED",
        "prompt_locked": "PROMPT_LOCKED",
        "processing": "GENERATING",
        "postcheck_passed": "POSTCHECK_PASSED",
        "postcheck_failed": "POSTCHECK_FAILED",
        "completed": "COMPLETE",
        "failed": "FAILED",
        "ai_max_retry_exceeded": "FAILED",
    }
    
    return {
        "id": str(job.id),
        "pageId": str(job.page_id),
        "pageTitle": page.title,
        "siteId": str(page.site_id),
        "status": status_map.get(job.status, job.status.upper()),
        "createdAt": job.created_at.isoformat() if job.created_at else None,
        "updatedAt": job.created_at.isoformat() if job.created_at else None,
        "costEstimate": job.total_cost_usd,
        "retries": job.retry_count,
    }
