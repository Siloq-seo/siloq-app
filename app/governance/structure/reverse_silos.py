"""Reverse Silos enforcement (3-7 silos per site)"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.db.models import Silo, Site
from app.core.config import settings


class ReverseSiloEnforcer:
    """Enforces structural constraints for Reverse Silos"""

    def __init__(
        self,
        min_silos: int = None,
        max_silos: int = None,
    ):
        self.min_silos = min_silos or settings.min_reverse_silos
        self.max_silos = max_silos or settings.max_reverse_silos

    async def get_silo_count(self, db: AsyncSession, site_id: str) -> int:
        """Get current number of silos for a site"""
        query = select(func.count(Silo.id)).where(Silo.site_id == site_id)
        result = await db.execute(query)
        return result.scalar() or 0

    async def can_add_silo(self, db: AsyncSession, site_id: str) -> tuple[bool, str]:
        """
        Check if a new silo can be added
        
        Returns:
            (can_add: bool, reason: str)
        """
        count = await self.get_silo_count(db, site_id)

        if count >= self.max_silos:
            return (
                False,
                f"Maximum silos ({self.max_silos}) reached. Cannot add more silos.",
            )

        return (True, "")

    async def validate_silo_structure(
        self, db: AsyncSession, site_id: str
    ) -> tuple[bool, str]:
        """
        Validate that site has valid silo structure (3-7 silos)
        
        Returns:
            (is_valid: bool, message: str)
        """
        count = await self.get_silo_count(db, site_id)

        if count < self.min_silos:
            return (
                False,
                f"Site must have at least {self.min_silos} silos. Currently has {count}.",
            )

        if count > self.max_silos:
            return (
                False,
                f"Site cannot have more than {self.max_silos} silos. Currently has {count}.",
            )

        return (True, f"Site has {count} silos (valid range: {self.min_silos}-{self.max_silos})")

    async def get_next_position(self, db: AsyncSession, site_id: str) -> int:
        """Get the next position number for a new silo"""
        query = select(func.max(Silo.position)).where(Silo.site_id == site_id)
        result = await db.execute(query)
        max_position = result.scalar()
        return (max_position or 0) + 1

    async def create_silo(
        self,
        db: AsyncSession,
        site_id: str,
        name: str,
        slug: str,
    ) -> tuple[Optional[Silo], bool, str]:
        """
        Create a new silo with structure validation
        
        Returns:
            (silo: Optional[Silo], success: bool, message: str)
        """
        can_add, reason = await self.can_add_silo(db, site_id)
        if not can_add:
            return (None, False, reason)

        position = await self.get_next_position(db, site_id)

        silo = Silo(
            site_id=site_id,
            name=name,
            slug=slug,
            position=position,
        )

        try:
            db.add(silo)
            await db.commit()
            await db.refresh(silo)
            return (silo, True, f"Silo created at position {position}")
        except IntegrityError as e:
            await db.rollback()
            return (None, False, f"Failed to create silo: {str(e)}")

    async def get_silos_for_site(
        self, db: AsyncSession, site_id: str
    ) -> List[Silo]:
        """Get all silos for a site, ordered by position"""
        query = select(Silo).where(Silo.site_id == site_id).order_by(Silo.position)
        result = await db.execute(query)
        return list(result.scalars().all())

