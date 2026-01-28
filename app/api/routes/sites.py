"""Site management routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.core.auth import get_current_user, verify_site_access
from app.db.models import Site, Page, GenerationJob
from app.schemas.sites import SiteCreate, SiteResponse

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", response_model=List[SiteResponse])
async def list_sites(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all sites.
    
    Args:
        db: Database session
        
    Returns:
        List of sites
    """
    query = select(Site).order_by(Site.created_at.desc())
    result = await db.execute(query)
    sites = result.scalars().all()
    
    # Format response with additional dashboard fields
    sites_list = []
    for site in sites:
        # Count pages for this site
        pages_query = select(func.count(Page.id)).where(Page.site_id == site.id)
        pages_result = await db.execute(pages_query)
        page_count = pages_result.scalar() or 0
        
        # Count active content jobs
        jobs_query = select(func.count(GenerationJob.id)).join(Page).where(
            Page.site_id == site.id,
            GenerationJob.status.in_(["draft", "preflight_approved", "prompt_locked", "processing"])
        )
        jobs_result = await db.execute(jobs_query)
        active_jobs = jobs_result.scalar() or 0
        
        # Calculate silo health score (simplified - in real implementation, calculate from silo structure)
        silo_health_score = 85  # Default score
        
        sites_list.append({
            "id": str(site.id),
            "name": site.name,
            "url": site.domain,
            "status": "connected",  # Default status
            "lastSyncAt": None,  # Would come from sync tracking
            "syncError": None,
            "siloHealthScore": silo_health_score,
            "activeContentJobs": active_jobs,
            "pageCount": page_count,
        })
    
    return sites_list


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SiteResponse)
async def create_site(
    site_data: SiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new site.
    
    Args:
        site_data: Site creation data (name and domain)
        db: Database session
        
    Returns:
        Created site with ID
    """
    # In a future enhancement, we will associate sites with the authenticated
    # account/organization to enforce ownership at the data model level.
    site = Site(name=site_data.name, domain=site_data.domain)
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    site: Site = Depends(verify_site_access),
):
    """
    Get site details by ID.
    
    Args:
        site_id: Site UUID
        db: Database session
        
    Returns:
        Site data
    """
    # Site existence and tenant access are enforced by verify_site_access
    return site


@router.get("/{site_id}/pages")
async def get_site_pages(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    site: Site = Depends(verify_site_access),
):
    """
    Get all pages for a site.
    
    Args:
        site_id: Site UUID
        db: Database session
        
    Returns:
        List of pages for the site
    """
    from app.db.models import Page, Keyword, PageSilo, Silo
    from app.schemas.pages import PageResponse
    
    pages_query = select(Page).where(Page.site_id == site_id).order_by(Page.created_at.desc())
    pages_result = await db.execute(pages_query)
    pages = pages_result.scalars().all()
    
    # Format pages for dashboard
    pages_list = []
    for page in pages:
        # Get keyword if exists
        keyword_query = select(Keyword).where(Keyword.page_id == page.id)
        keyword_result = await db.execute(keyword_query)
        keyword = keyword_result.scalar_one_or_none()
        
        # Get silos for this page
        silos_query = select(Silo).join(PageSilo).where(PageSilo.page_id == page.id)
        silos_result = await db.execute(silos_query)
        silos = silos_result.scalars().all()
        silo_id = str(silos[0].id) if silos else None
        
        # Determine page type from governance_checks or default
        page_type = "Supporting"  # Default
        if page.governance_checks and "page_type" in page.governance_checks:
            page_type = page.governance_checks["page_type"]
        elif keyword:
            page_type = "Target"
        
        # Determine compliance status
        compliance_status = "compliant"  # Default
        if page.governance_checks:
            if page.governance_checks.get("violations"):
                compliance_status = "violation"
            elif page.governance_checks.get("warnings"):
                compliance_status = "warning"
        
        # Extract entities
        entities = []
        if page.governance_checks and "entities" in page.governance_checks:
            entities = page.governance_checks["entities"]
        
        # Count links (simplified - would need to parse body or store separately)
        inbound_links = 0
        outbound_links = 0
        if page.body:
            # Simple count of links in body (very basic)
            outbound_links = page.body.count('<a href')
        
        pages_list.append({
            "id": str(page.id),
            "siteId": str(page.site_id),
            "title": page.title,
            "url": f"https://{site.domain}{page.path}" if site.domain else page.path,
            "path": page.path,
            "pageType": page_type,
            "siloId": silo_id,
            "complianceStatus": compliance_status,
            "lastModified": page.updated_at.isoformat() if page.updated_at else page.created_at.isoformat(),
            "entities": entities,
            "inboundLinks": inbound_links,
            "outboundLinks": outbound_links,
            "cannibalizationIssues": None,  # Would need to query CannibalizationCheck
        })
    
    return pages_list

