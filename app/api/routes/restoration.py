"""Restoration queue management routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user
from app.db.models import Page, Site, ContentStatus

router = APIRouter(prefix="/restoration-queue", tags=["restoration-queue"])


class RestorationJobCreate(BaseModel):
    siteId: str
    priority: Optional[str] = "medium"  # low, medium, high, critical


@router.get("")
async def list_restoration_queue(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all restoration jobs in the queue.
    
    Returns:
        List of restoration jobs with status and progress
    """
    # Find pages that need restoration (DECOMMISSIONED status)
    pages_query = select(Page).where(Page.status == ContentStatus.DECOMMISSIONED)
    pages_result = await db.execute(pages_query)
    decommissioned_pages = pages_result.scalars().all()
    
    # Group by site
    site_pages = {}
    for page in decommissioned_pages:
        site_id_str = str(page.site_id)
        if site_id_str not in site_pages:
            site_pages[site_id_str] = []
        site_pages[site_id_str].append(page)
    
    # Create restoration jobs for each site
    restoration_jobs = []
    for site_id_str, pages in site_pages.items():
        site = await db.get(Site, UUID(site_id_str))
        if not site:
            continue
        
        # Calculate progress (for now, all are pending)
        total_pages = len(pages)
        restored_pages = 0  # In a real implementation, track this
        
        restoration_jobs.append({
            "id": site_id_str,  # Using site_id as job ID for now
            "siteId": site_id_str,
            "siteName": site.name or site.domain,
            "status": "pending",  # pending, in_progress, completed, failed
            "priority": "medium",  # low, medium, high, critical
            "createdAt": min([p.decommissioned_at.isoformat() for p in pages if p.decommissioned_at] or [datetime.now().isoformat()]),
            "startedAt": None,
            "completedAt": None,
            "progress": int((restored_pages / total_pages * 100)) if total_pages > 0 else 0,
            "pagesToRestore": total_pages,
            "pagesRestored": restored_pages,
            "error": None,
            "estimatedCompletion": None,
        })
    
    # Sort by priority and creation date
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    restoration_jobs.sort(key=lambda x: (priority_order.get(x["priority"], 99), x["createdAt"]))
    
    return restoration_jobs


@router.post("")
async def create_restoration_job(
    job_data: RestorationJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new restoration job for a site.
    
    Args:
        job_data: Restoration job data (siteId, priority)
        
    Returns:
        Created restoration job
        
    Raises:
        HTTPException: 404 if site not found
    """
    try:
        site_uuid = UUID(job_data.siteId) if isinstance(job_data.siteId, str) else job_data.siteId
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid siteId format")
    
    site = await db.get(Site, site_uuid)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Find decommissioned pages for this site
    pages_query = select(Page).where(
        Page.site_id == site_uuid,
        Page.status == ContentStatus.DECOMMISSIONED
    )
    pages_result = await db.execute(pages_query)
    pages = pages_result.scalars().all()
    
    if not pages:
        raise HTTPException(status_code=400, detail="No decommissioned pages found for this site")
    
    # Create restoration job (in a real implementation, this would create a job record)
    # For now, we'll return the job structure
    total_pages = len(pages)
    
    return {
        "id": str(site_uuid),
        "siteId": str(site_uuid),
        "siteName": site.name or site.domain,
        "status": "pending",
        "priority": job_data.priority,
        "createdAt": datetime.now().isoformat(),
        "startedAt": None,
        "completedAt": None,
        "progress": 0,
        "pagesToRestore": total_pages,
        "pagesRestored": 0,
        "error": None,
        "estimatedCompletion": None,
    }


@router.delete("/{job_id}")
async def cancel_restoration_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Cancel a restoration job.
    
    Args:
        job_id: Restoration job ID (site ID)
        
    Returns:
        Success message
        
    Raises:
        HTTPException: 404 if job not found
    """
    try:
        site_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    site = await db.get(Site, site_uuid)
    if not site:
        raise HTTPException(status_code=404, detail="Restoration job not found")
    
    # In a real implementation, this would cancel the job
    # For now, we'll just return success
    return {
        "success": True,
        "message": "Restoration job cancelled",
        "jobId": job_id,
    }
