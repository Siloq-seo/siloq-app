"""Silo management routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.db.models import Site
from app.api.dependencies import get_silo_enforcer
from app.schemas.sites import SiloCreate, SiloResponse
from app.governance.structure.silo_batch_publishing import SiloBatchPublisher

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


@router.post("/{silo_id}/publish-batch")
async def publish_silo_batch(
    site_id: UUID,
    silo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish entire silo as a batch (atomic unit).
    
    Strategy Update: The "Atomic Unit" of publishing is the SILO, not the page.
    When a silo is finalized, publish all pages simultaneously so they link instantly.
    
    Site Age Governor:
    - Brand New Sites (<1 Year): Heartbeat Drip - 1 Full Silo per Week
    - Established Sites (>1 Year): No speed limit - publish immediately when finalized
    
    Args:
        site_id: Site UUID
        silo_id: Silo UUID
        db: Database session
        
    Returns:
        Batch publishing result with published pages
        
    Raises:
        HTTPException: 404 if site/silo not found, 400 if cannot publish
    """
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    publisher = SiloBatchPublisher()
    result = await publisher.publish_silo_batch(db, str(silo_id))
    
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("reason", "Cannot publish silo"),
        )
    
    return result


@router.get("/{silo_id}/publish-status")
async def get_silo_publish_status(
    site_id: UUID,
    silo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get publishing status for a silo.
    
    Returns comprehensive status including:
    - Finalization status
    - Page readiness (gates passed)
    - Site age and speed limit status
    - Next available publish time (for new sites)
    
    Args:
        site_id: Site UUID
        silo_id: Silo UUID
        db: Database session
        
    Returns:
        Silo publish status
        
    Raises:
        HTTPException: 404 if site/silo not found
    """
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    publisher = SiloBatchPublisher()
    status_result = await publisher.get_silo_publish_status(db, str(silo_id))
    
    if "error" in status_result:
        raise HTTPException(status_code=404, detail=status_result["error"])
    
    return status_result
