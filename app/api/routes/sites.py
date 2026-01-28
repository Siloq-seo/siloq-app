"""Site management routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.core.auth import get_current_user, verify_site_access
from app.db.models import Site
from app.schemas.sites import SiteCreate, SiteResponse

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", status_code=status.HTTP_201_CREATED, response_model=SiteResponse)
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

