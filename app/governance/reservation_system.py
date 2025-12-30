"""Reservation system for planning collision prevention."""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.models import Page, Site, ContentReservation


class ContentReservation:
    """Represents a content slot reservation."""
    
    def __init__(
        self,
        reservation_id: UUID,
        site_id: UUID,
        intent_hash: str,
        location: Optional[str],
        expires_at: datetime,
        page_id: Optional[UUID] = None,
    ):
        self.reservation_id = reservation_id
        self.site_id = site_id
        self.intent_hash = intent_hash
        self.location = location
        self.expires_at = expires_at
        self.page_id = page_id
    
    def is_expired(self) -> bool:
        """Check if reservation has expired."""
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "reservation_id": str(self.reservation_id),
            "site_id": str(self.site_id),
            "intent_hash": self.intent_hash,
            "location": self.location,
            "expires_at": self.expires_at.isoformat(),
            "page_id": str(self.page_id) if self.page_id else None,
            "is_expired": self.is_expired(),
        }


class ReservationSystem:
    """
    Manages content slot reservations to prevent planning collisions.
    
    Allows reserving content slots before generation to prevent
    multiple planners from creating duplicate content.
    """
    
    DEFAULT_EXPIRATION_DAYS = 7
    
    @staticmethod
    def _hash_intent(title: str, location: Optional[str] = None) -> str:
        """
        Create deterministic hash for content intent.
        
        Args:
            title: Content title
            location: Optional location
            
        Returns:
            Hash string representing intent
        """
        import hashlib
        
        # Normalize inputs
        normalized_title = title.lower().strip()
        normalized_location = location.lower().strip() if location else ""
        
        # Create hash
        intent_string = f"{normalized_title}|{normalized_location}"
        return hashlib.md5(intent_string.encode()).hexdigest()
    
    async def reserve_content_slot(
        self,
        db: AsyncSession,
        site_id: UUID,
        title: str,
        location: Optional[str] = None,
        expiration_days: int = None,
    ) -> Tuple[Optional[ContentReservation], bool, str]:
        """
        Reserve a content slot for planning.
        
        Args:
            db: Database session
            site_id: Site identifier
            title: Content title
            location: Optional location
            expiration_days: Reservation expiration in days
            
        Returns:
            Tuple of (reservation, success, message)
        """
        expiration_days = expiration_days or self.DEFAULT_EXPIRATION_DAYS
        intent_hash = self._hash_intent(title, location)
        
        # Check for existing active reservation
        existing = await self._find_active_reservation(
            db, site_id, intent_hash, location
        )
        
        if existing:
            return (
                None,
                False,
                f"Content slot already reserved (expires: {existing.expires_at.isoformat()})",
            )
        
        # Create reservation in database
        from uuid import uuid4
        
        reservation_id = uuid4()
        expires_at = datetime.utcnow() + timedelta(days=expiration_days)
        
        db_reservation = ContentReservation(
            id=reservation_id,
            site_id=site_id,
            intent_hash=intent_hash,
            location=location,
            expires_at=expires_at,
        )
        db.add(db_reservation)
        await db.commit()
        await db.refresh(db_reservation)
        
        reservation = ContentReservation(
            reservation_id=db_reservation.id,
            site_id=db_reservation.site_id,
            intent_hash=db_reservation.intent_hash,
            location=db_reservation.location,
            expires_at=db_reservation.expires_at,
        )
        
        return reservation, True, "Reservation created"
    
    async def check_reservation_conflict(
        self,
        db: AsyncSession,
        site_id: UUID,
        title: str,
        location: Optional[str] = None,
    ) -> Tuple[bool, Optional[ContentReservation]]:
        """
        Check if content would conflict with existing reservation.
        
        Args:
            db: Database session
            site_id: Site identifier
            title: Content title
            location: Optional location
            
        Returns:
            Tuple of (has_conflict, conflicting_reservation)
        """
        intent_hash = self._hash_intent(title, location)
        
        existing = await self._find_active_reservation(
            db, site_id, intent_hash, location
        )
        
        if existing and not existing.is_expired():
            return True, existing
        
        return False, None
    
    async def release_reservation(
        self, db: AsyncSession, reservation_id: UUID
    ) -> Tuple[bool, str]:
        """
        Release a content reservation.
        
        Args:
            db: Database session
            reservation_id: Reservation identifier
            
        Returns:
            Tuple of (success, message)
        """
        reservation = await db.get(ContentReservation, reservation_id)
        if not reservation:
            return False, "Reservation not found"
        
        # Delete the reservation
        await db.delete(reservation)
        await db.commit()
        
        return True, "Reservation released"
    
    async def _find_active_reservation(
        self,
        db: AsyncSession,
        site_id: UUID,
        intent_hash: str,
        location: Optional[str],
    ) -> Optional[ContentReservation]:
        """
        Find active reservation matching intent.
        
        Args:
            db: Database session
            site_id: Site identifier
            intent_hash: Intent hash
            location: Optional location
            
        Returns:
            ContentReservation if found, None otherwise
        """
        # Query active reservations
        query = select(ContentReservation).where(
            and_(
                ContentReservation.site_id == site_id,
                ContentReservation.intent_hash == intent_hash,
                ContentReservation.location == location if location else ContentReservation.location.is_(None),
                ContentReservation.expires_at > datetime.utcnow(),
                ContentReservation.fulfilled_at.is_(None),
            )
        )
        
        result = await db.execute(query)
        db_reservation = result.scalar_one_or_none()
        
        if db_reservation:
            return ContentReservation(
                reservation_id=db_reservation.id,
                site_id=db_reservation.site_id,
                intent_hash=db_reservation.intent_hash,
                location=db_reservation.location,
                expires_at=db_reservation.expires_at,
                page_id=db_reservation.page_id,
            )
        
        return None
    
    async def cleanup_expired_reservations(
        self, db: AsyncSession, site_id: Optional[UUID] = None
    ) -> int:
        """
        Clean up expired reservations.
        
        Args:
            db: Database session
            site_id: Optional site ID to limit cleanup
            
        Returns:
            Number of reservations cleaned up
        """
        query = select(ContentReservation).where(
            and_(
                ContentReservation.expires_at < datetime.utcnow(),
                ContentReservation.fulfilled_at.is_(None),
            )
        )
        
        if site_id:
            query = query.where(ContentReservation.site_id == site_id)
        
        result = await db.execute(query)
        expired_reservations = result.scalars().all()
        
        count = 0
        for reservation in expired_reservations:
            await db.delete(reservation)
            count += 1
        
        await db.commit()
        return count

