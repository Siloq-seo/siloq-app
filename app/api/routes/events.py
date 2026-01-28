"""System events routes"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.auth import get_current_user
from app.db.models import SystemEvent, Site

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def list_system_events(
    eventType: Optional[str] = Query(None, alias="eventType", description="Filter by event type"),
    siteId: Optional[UUID] = Query(None, alias="siteId", description="Filter by site ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events to return"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List system events (audit log).
    
    Args:
        eventType: Optional event type filter
        siteId: Optional site ID filter
        limit: Maximum number of events to return (1-1000)
        
    Returns:
        List of system events
    """
    query = select(SystemEvent)
    
    # Apply filters
    if eventType:
        query = query.where(SystemEvent.event_type == eventType)
    
    if siteId:
        # Filter by site through project_id or target_entity_id
        # In a real implementation, you'd need to join with sites/projects
        # For now, we'll filter by target_entity_id if it matches a site
        query = query.where(
            (SystemEvent.target_entity_type == "site") &
            (SystemEvent.target_entity_id == siteId)
        )
    
    # Order by created_at descending (most recent first)
    query = query.order_by(SystemEvent.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    # Format response to match dashboard expectations
    events_list = []
    for event in events:
        events_list.append({
            "id": str(event.id),
            "timestamp": event.created_at.isoformat() if event.created_at else None,
            "eventType": event.event_type,
            "actor": event.actor_id.hex if event.actor_id else "system",
            "resourceType": event.target_entity_type or "unknown",
            "resourceId": str(event.target_entity_id) if event.target_entity_id else None,
            "details": event.payload or {},
        })
    
    return events_list
