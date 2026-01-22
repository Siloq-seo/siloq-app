"""Authority funnel management for reverse silos."""
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.db.models import Silo, Page, PageSilo

# Constants
HUB_AUTHORITY_WEIGHT = 0.7
SUPPORTING_AUTHORITY_WEIGHT = 0.3
MIN_AUTHORITY_SCORE = 0.0
MAX_AUTHORITY_SCORE = 1.0
PUBLISHED_STATUSES = ["published", "approved"]


class AuthorityFunnel:
    """
    Manages authority funnels for reverse silos.
    
    Ensures authority flows correctly through silos:
    - Hub pages receive authority from supporting pages
    - Authority flows downward, not sideways
    - Entity inheritance maintains structure
    """
    
    @staticmethod
    async def calculate_silo_authority(
        db: AsyncSession,
        silo_id: UUID,
    ) -> float:
        """
        Calculate authority funnel score for a silo.
        
        Combines hub page authority (70%) with weighted supporting page
        authority (30%) to create a comprehensive silo authority score.
        
        Args:
            db: Database session
            silo_id: Silo identifier
            
        Returns:
            Authority funnel score between 0.0 and 1.0
        """
        # Get all published pages in silo
        pages = await AuthorityFunnel._get_silo_pages(db, silo_id)
        
        if not pages:
            return MIN_AUTHORITY_SCORE
        
        # Calculate average authority from hub pages
        hub_authority = AuthorityFunnel._calculate_hub_authority(pages)
        
        # Calculate weighted authority from supporting pages
        supporting_authority = await AuthorityFunnel._calculate_supporting_authority(
            db, silo_id
        )
        
        # Combine hub and supporting authority
        total_score = (hub_authority * HUB_AUTHORITY_WEIGHT) + (
            supporting_authority * SUPPORTING_AUTHORITY_WEIGHT
        )
        
        return min(MAX_AUTHORITY_SCORE, max(MIN_AUTHORITY_SCORE, total_score))
    
    @staticmethod
    async def _get_silo_pages(
        db: AsyncSession,
        silo_id: UUID,
    ) -> list[Page]:
        """Get all published pages in a silo."""
        query = (
            select(Page)
            .join(PageSilo, Page.id == PageSilo.page_id)
            .where(
                and_(
                    PageSilo.silo_id == silo_id,
                    Page.status.in_(PUBLISHED_STATUSES),
                )
            )
        )
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    def _calculate_hub_authority(pages: list[Page]) -> float:
        """Calculate average authority score from hub pages."""
        if not pages:
            return MIN_AUTHORITY_SCORE
        
        total_authority = sum(page.authority_score or MIN_AUTHORITY_SCORE for page in pages)
        return total_authority / len(pages)
    
    @staticmethod
    async def _calculate_supporting_authority(
        db: AsyncSession,
        silo_id: UUID,
    ) -> float:
        """Calculate weighted authority from supporting pages."""
        query = (
            select(PageSilo, Page)
            .join(Page, PageSilo.page_id == Page.id)
            .where(
                and_(
                    PageSilo.silo_id == silo_id,
                    PageSilo.is_supporting_page == True,
                )
            )
        )
        
        result = await db.execute(query)
        supporting_pages = result.all()
        
        if not supporting_pages:
            return MIN_AUTHORITY_SCORE
        
        total_weighted_authority = sum(
            page_silo.authority_weight * (page.authority_score or MIN_AUTHORITY_SCORE)
            for page_silo, page in supporting_pages
        )
        
        return total_weighted_authority
    
    @staticmethod
    async def update_silo_authority(
        db: AsyncSession,
        silo_id: UUID,
    ) -> float:
        """
        Update and store authority funnel score for a silo.
        
        Args:
            db: Database session
            silo_id: Silo identifier
            
        Returns:
            Updated authority score
        """
        score = await AuthorityFunnel.calculate_silo_authority(db, silo_id)
        
        silo = await db.get(Silo, silo_id)
        if silo:
            silo.authority_funnel_score = score
            await db.commit()
            await db.refresh(silo)
        
        return score
    
    @staticmethod
    async def get_entity_inheritance(
        db: AsyncSession,
        silo_id: UUID,
    ) -> Dict[str, any]:
        """
        Get entity inheritance structure for a silo.
        
        Returns information about parent-child relationships and
        entity types for hierarchical silo structures.
        
        Args:
            db: Database session
            silo_id: Silo identifier
            
        Returns:
            Dictionary with inheritance information including:
            - silo_id: Current silo identifier
            - entity_type: Type of entity (topic, category, service, etc.)
            - parent_silo_id: Parent silo identifier if exists
            - parent_entity_type: Parent entity type if exists
            - authority_score: Current authority funnel score
            - child_silos: List of child silos
        """
        silo = await db.get(Silo, silo_id)
        if not silo:
            return {}
        
        inheritance: Dict[str, any] = {
            "silo_id": str(silo.id),
            "entity_type": silo.entity_type,
            "parent_silo_id": str(silo.parent_silo_id) if silo.parent_silo_id else None,
            "authority_score": silo.authority_funnel_score or MIN_AUTHORITY_SCORE,
        }
        
        # Get parent entity type if parent exists
        if silo.parent_silo_id:
            parent = await db.get(Silo, silo.parent_silo_id)
            if parent:
                inheritance["parent_entity_type"] = parent.entity_type
        
        # Get child silos
        child_silos = await AuthorityFunnel._get_child_silos(db, silo_id)
        inheritance["child_silos"] = [
            {
                "id": str(child.id),
                "name": child.name,
                "entity_type": child.entity_type,
            }
            for child in child_silos
        ]
        
        return inheritance
    
    @staticmethod
    async def _get_child_silos(
        db: AsyncSession,
        silo_id: UUID,
    ) -> list[Silo]:
        """Get all child silos for a given silo."""
        query = select(Silo).where(Silo.parent_silo_id == silo_id)
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def validate_authority_flow(
        db: AsyncSession,
        from_page_id: UUID,
        to_page_id: UUID,
    ) -> Tuple[bool, str]:
        """
        Validate that authority flow is allowed between two pages.
        
        Prevents sideways authority leakage by checking if pages are in
        different silos with anchor governance enabled.
        
        Args:
            db: Database session
            from_page_id: Source page identifier
            to_page_id: Target page identifier
            
        Returns:
            Tuple of (is_valid, reason_message)
        """
        from_silo_ids = await AuthorityFunnel._get_page_silo_ids(db, from_page_id)
        to_silo_ids = await AuthorityFunnel._get_page_silo_ids(db, to_page_id)
        
        # If pages share a silo, flow is always allowed
        if from_silo_ids.intersection(to_silo_ids):
            return (True, "Authority flow allowed")
        
        # If pages are in different silos, check governance
        if from_silo_ids and to_silo_ids:
            is_blocked = await AuthorityFunnel._check_sideways_leakage(
                db, from_silo_ids, to_silo_ids
            )
            
            if is_blocked:
                return (
                    False,
                    "Sideways authority leakage blocked: Anchor governance enabled",
                )
        
        return (True, "Authority flow allowed")
    
    @staticmethod
    async def _get_page_silo_ids(
        db: AsyncSession,
        page_id: UUID,
    ) -> set[UUID]:
        """Get set of silo IDs for a page."""
        query = select(PageSilo.silo_id).where(PageSilo.page_id == page_id)
        result = await db.execute(query)
        return {silo_id for silo_id, in result.all()}
    
    @staticmethod
    async def _check_sideways_leakage(
        db: AsyncSession,
        from_silo_ids: set[UUID],
        to_silo_ids: set[UUID],
    ) -> bool:
        """Check if sideways leakage would occur between silos."""
        all_silo_ids = from_silo_ids.union(to_silo_ids)
        
        query = select(Silo).where(Silo.id.in_(all_silo_ids))
        result = await db.execute(query)
        silos = result.scalars().all()
        
        # If any silo has anchor governance enabled, block sideways flow
        return any(silo.anchor_governance_enabled for silo in silos)
