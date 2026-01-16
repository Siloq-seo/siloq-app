"""Silo finalization logic for locking silo structure."""
from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.db.models import Silo, Page, PageSilo
from app.governance.reverse_silos import ReverseSiloEnforcer
from app.governance.authority_funnel import AuthorityFunnel
from uuid import UUID

# Constants
MIN_PAGES_FOR_FINALIZATION = 3
UNPUBLISHED_STATUSES = ["draft", "pending_review"]


class SiloFinalizer:
    """
    Handles silo finalization logic.
    
    Once a silo is finalized:
    - Structure is locked (no more pages can be added)
    - Authority funnel is calculated and stored
    - Entity inheritance is established
    - Proposal buffering is resolved
    """
    
    def __init__(self):
        """Initialize silo finalizer with dependencies."""
        self.silo_enforcer = ReverseSiloEnforcer()
    
    async def can_finalize_silo(
        self,
        db: AsyncSession,
        silo_id: UUID,
    ) -> Tuple[bool, List[str]]:
        """
        Check if a silo can be finalized.
        
        Validates:
        - Silo exists and is not already finalized
        - Minimum page count requirement
        - No unpublished proposals
        - Site silo structure is valid
        
        Args:
            db: Database session
            silo_id: Silo identifier
            
        Returns:
            Tuple of (can_finalize, blocking_reasons)
        """
        reasons: List[str] = []
        silo = await db.get(Silo, silo_id)
        
        if not silo:
            return (False, ["Silo not found"])
        
        if silo.is_finalized:
            return (False, ["Silo is already finalized"])
        
        # Check minimum pages requirement
        page_count = await self._get_silo_page_count(db, silo_id)
        if page_count < MIN_PAGES_FOR_FINALIZATION:
            reasons.append(
                f"Silo must have at least {MIN_PAGES_FOR_FINALIZATION} pages. "
                f"Currently has {page_count}"
            )
        
        # Check for unpublished proposals
        proposal_count = await self._get_unpublished_proposal_count(db, silo_id)
        if proposal_count > 0:
            reasons.append(
                f"Silo has {proposal_count} unpublished proposal(s). "
                "Publish or remove proposals before finalizing."
            )
        
        # Check site silo structure
        site_valid, site_message = await self.silo_enforcer.validate_silo_structure(
            db, str(silo.site_id)
        )
        if not site_valid:
            reasons.append(f"Site structure invalid: {site_message}")
        
        return (len(reasons) == 0, reasons)
    
    async def _get_silo_page_count(
        self,
        db: AsyncSession,
        silo_id: UUID,
    ) -> int:
        """Get count of pages in a silo."""
        query = select(func.count(PageSilo.page_id)).where(PageSilo.silo_id == silo_id)
        result = await db.execute(query)
        return result.scalar() or 0
    
    async def _get_unpublished_proposal_count(
        self,
        db: AsyncSession,
        silo_id: UUID,
    ) -> int:
        """Get count of unpublished proposals in a silo."""
        query = (
            select(func.count(Page.id))
            .join(PageSilo, Page.id == PageSilo.page_id)
            .where(
                and_(
                    PageSilo.silo_id == silo_id,
                    Page.is_proposal == True,
                    Page.status.in_(UNPUBLISHED_STATUSES),
                )
            )
        )
        
        result = await db.execute(query)
        return result.scalar() or 0
    
    async def finalize_silo(
        self,
        db: AsyncSession,
        silo_id: UUID,
    ) -> Tuple[bool, str, Dict]:
        """
        Finalize a silo structure.
        
        Calculates authority funnel, establishes entity inheritance,
        and locks the silo structure.
        
        Args:
            db: Database session
            silo_id: Silo identifier
            
        Returns:
            Tuple of (success, message, finalization_data)
        """
        can_finalize, reasons = await self.can_finalize_silo(db, silo_id)
        
        if not can_finalize:
            return (False, "; ".join(reasons), {})
        
        silo = await db.get(Silo, silo_id)
        if not silo:
            return (False, "Silo not found", {})
        
        # Calculate and update authority funnel
        authority_score = await AuthorityFunnel.update_silo_authority(db, silo_id)
        
        # Get entity inheritance structure
        inheritance = await AuthorityFunnel.get_entity_inheritance(db, silo_id)
        
        # Finalize silo
        silo.is_finalized = True
        silo.finalized_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(silo)
        
        finalization_data = {
            "silo_id": str(silo.id),
            "finalized_at": silo.finalized_at.isoformat(),
            "authority_funnel_score": authority_score,
            "entity_inheritance": inheritance,
        }
        
        return (True, "Silo finalized successfully", finalization_data)
    
    async def get_finalization_status(
        self,
        db: AsyncSession,
        silo_id: UUID,
    ) -> Dict:
        """
        Get finalization status for a silo.
        
        Provides comprehensive status including:
        - Current finalization state
        - Blocking reasons if not ready
        - Page and proposal counts
        - Authority funnel score
        
        Args:
            db: Database session
            silo_id: Silo identifier
            
        Returns:
            Dictionary with finalization status information
        """
        silo = await db.get(Silo, silo_id)
        if not silo:
            return {"error": "Silo not found"}
        
        can_finalize, reasons = await self.can_finalize_silo(db, silo_id)
        page_count = await self._get_silo_page_count(db, silo_id)
        proposal_count = await self._get_unpublished_proposal_count(db, silo_id)
        
        return {
            "silo_id": str(silo.id),
            "is_finalized": silo.is_finalized,
            "finalized_at": silo.finalized_at.isoformat() if silo.finalized_at else None,
            "can_finalize": can_finalize,
            "blocking_reasons": reasons,
            "page_count": page_count,
            "proposal_count": proposal_count,
            "authority_funnel_score": silo.authority_funnel_score or 0.0,
        }
