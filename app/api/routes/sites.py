"""Site management routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import List, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, AnyHttpUrl
from datetime import datetime
import secrets

from app.core.database import get_db
from app.core.auth import get_current_user, verify_site_access, hash_api_key
from app.db.models import Site, Page, GenerationJob, APIKey
from app.schemas.sites import SiteResponse

router = APIRouter(prefix="/sites", tags=["sites"])


class DashboardSiteCreate(BaseModel):
    """
    Payload used by siloq-dashboard when creating a site.

    Example:
    {
      "url": "https://siloq.ai/",
      "name": "Siloq"
    }
    """

    url: AnyHttpUrl
    name: Optional[str] = None


@router.get("")
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

        # Get latest active API key (masked for display)
        api_key_display: Optional[str] = None
        api_key_query = (
            select(APIKey)
            .where(APIKey.site_id == site.id, APIKey.is_active.is_(True))
            .order_by(APIKey.created_at.desc())
        )
        api_key_result = await db.execute(api_key_query)
        latest_key = api_key_result.scalars().first()
        if latest_key:
            # Build a display string like "sk-xxxx..." from key_prefix
            api_key_display = f"sk-{latest_key.key_prefix}"
        
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
            "apiKey": api_key_display,
        })
    
    return sites_list


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SiteResponse)
async def create_site(
    site_data: DashboardSiteCreate,
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
    # Derive domain from URL
    parsed = urlparse(str(site_data.url))
    domain = parsed.netloc or parsed.path  # handles cases like "example.com"
    if not domain:
        raise HTTPException(status_code=400, detail="Invalid site URL")

    # Use provided name or fall back to domain
    name = site_data.name or domain

    # In a future enhancement, we will associate sites with the authenticated
    # account/organization to enforce ownership at the data model level.
    site = Site(name=name, domain=domain)
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


@router.post("/{site_id}/api-key")
async def generate_site_api_key(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    site: Site = Depends(verify_site_access),
):
    """
    Generate a new API key for a site.

    This is a convenience wrapper used by the dashboard, so it doesn't have to
    know about the lower-level /api-keys endpoint.

    Returns a masked key prefix suitable for display in the UI.
    """
    # Optional: revoke existing active keys for this site
    existing_keys_result = await db.execute(
        select(APIKey).where(APIKey.site_id == site_id, APIKey.is_active.is_(True))
    )
    existing_keys = existing_keys_result.scalars().all()
    now = datetime.utcnow()
    for key in existing_keys:
        key.is_active = False
        key.revoked_at = now
        key.revoked_reason = "Revoked by dashboard API key regeneration"

    # Generate new API key (same logic as api_keys.generate_api_key)
    random_bytes = secrets.token_bytes(32)
    raw_key = random_bytes.hex()
    api_key = f"sk-{raw_key}"
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:8]  # first 8 chars for identification

    api_key_obj = APIKey(
        site_id=site_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="WordPress Plugin",  # descriptive name
        scopes=["read", "write"],
        expires_at=None,
    )

    db.add(api_key_obj)
    await db.commit()
    await db.refresh(api_key_obj)

    # Return masked key for UI; full key should be copied immediately if needed
    return {
        "id": str(api_key_obj.id),
        "siteId": str(site_id),
        "apiKey": api_key,          # full key (only time it's returned)
        "apiKeyPrefix": key_prefix, # for display
    }


@router.delete("/{site_id}/api-key")
async def revoke_site_api_keys(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    site: Site = Depends(verify_site_access),
):
    """
    Revoke all active API keys for a site.

    This matches the dashboard's `DELETE /sites/{siteId}/api-key` call.
    """
    result = await db.execute(
        select(APIKey).where(APIKey.site_id == site_id, APIKey.is_active.is_(True))
    )
    keys = result.scalars().all()

    if not keys:
        # Nothing to revoke, but treat as success so UI stays simple
        return {"success": True, "revoked": 0}

    now = datetime.utcnow()
    revoked_count = 0
    for key in keys:
        key.is_active = False
        key.revoked_at = now
        key.revoked_reason = "Revoked by dashboard"
        revoked_count += 1

    await db.commit()

    return {"success": True, "revoked": revoked_count}

