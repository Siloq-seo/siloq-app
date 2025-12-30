"""Silo management routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.db.models import Site
from app.api.dependencies import get_silo_enforcer
from app.schemas.sites import SiloCreate, SiloResponse

router = APIRouter(prefix="/sites/{site_id}/silos", tags=["silos"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SiloResponse)
async def create_silo(
    site_id: UUID,
    silo_data: SiloCreate,
    db: AsyncSession = Depends(get_db),
    silo_enforcer = Depends(get_silo_enforcer),
):
    """
    Create a new silo (enforces 3-7 limit).
    
    Args:
        site_id: Site UUID
        silo_data: Silo creation data (name and slug)
        db: Database session
        silo_enforcer: Reverse silo enforcer service
        
    Returns:
        Created silo with ID and position
        
    Raises:
        HTTPException: 404 if site not found, 400 if silo limit reached
    """
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Check if silo can be added
    can_add, reason = await silo_enforcer.can_add_silo(db, str(site_id))
    if not can_add:
        raise HTTPException(status_code=400, detail=reason)

    # Get next position
    position = await silo_enforcer.get_next_position(db, str(site_id))

    from app.db.models import Silo
    silo = Silo(
        name=silo_data.name,
        slug=silo_data.slug,
        site_id=site_id,
        position=position,
    )
    db.add(silo)
    await db.commit()
    await db.refresh(silo)
    return silo


@router.get("")
async def get_silos(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
    silo_enforcer = Depends(get_silo_enforcer),
):
    """
    Get all silos for a site.
    
    Args:
        site_id: Site UUID
        db: Database session
        silo_enforcer: Reverse silo enforcer service
        
    Returns:
        List of silos for the site
    """
    silos = await silo_enforcer.get_silos_for_site(db, str(site_id))
    return silos


@router.get("/validate")
async def validate_silo_structure(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
    silo_enforcer = Depends(get_silo_enforcer),
):
    """
    Validate silo structure (3-7 silos).
    
    Args:
        site_id: Site UUID
        db: Database session
        silo_enforcer: Reverse silo enforcer service
        
    Returns:
        Validation result with is_valid flag and message
    """
    is_valid, message = await silo_enforcer.validate_silo_structure(db, str(site_id))
    return {"is_valid": is_valid, "message": message}

