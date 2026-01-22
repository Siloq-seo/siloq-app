"""Database utility functions"""
from typing import Type, TypeVar, Optional
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')


async def get_or_404(
    db: AsyncSession,
    model: Type[T],
    entity_id: UUID,
    entity_name: Optional[str] = None
) -> T:
    """
    Generic helper to fetch entity or raise 404

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: UUID of the entity to fetch
        entity_name: Optional custom name for error message

    Returns:
        The entity instance

    Raises:
        HTTPException: 404 if entity not found

    Example:
        site = await get_or_404(db, Site, site_id, "Site")
    """
    entity = await db.get(model, entity_id)
    if not entity:
        name = entity_name or model.__name__
        raise HTTPException(
            status_code=404,
            detail=f"{name} not found"
        )
    return entity


async def get_or_none(
    db: AsyncSession,
    model: Type[T],
    entity_id: UUID
) -> Optional[T]:
    """
    Generic helper to fetch entity or return None

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: UUID of the entity to fetch

    Returns:
        The entity instance or None if not found

    Example:
        site = await get_or_none(db, Site, site_id)
        if site:
            # ... do something
    """
    return await db.get(model, entity_id)
