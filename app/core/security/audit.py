"""Enhanced immutable audit logging for all actions"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
import json

from app.db.models import SystemEvent, Project
from app.core.security.encryption import get_encryption_manager


class AuditLogger:
    """Immutable audit logger for system events"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption_manager = get_encryption_manager()
    
    async def create_event(
        self,
        event_type: str,
        severity: str,
        action: str,
        project_id: Optional[UUID] = None,
        actor_id: Optional[UUID] = None,
        actor_type: str = "user",
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
        target_entity_type: Optional[str] = None,
        target_entity_id: Optional[UUID] = None,
        payload: Optional[Dict[str, Any]] = None,
        doctrine_section: Optional[str] = None,
    ) -> SystemEvent:
        """
        Create an immutable audit log entry.
        
        Args:
            event_type: Type of event (e.g., "VALIDATION_RUN", "GENERATION_ATTEMPT")
            severity: Severity level (INFO, WARN, BLOCK, CRITICAL)
            action: Action description
            project_id: Project UUID (required for tenant isolation)
            actor_id: Actor UUID (user or null for system)
            actor_type: Actor type (user, system, agent)
            actor_ip: Actor IP address
            actor_user_agent: Actor user agent
            target_entity_type: Target entity type (e.g., "page", "silo")
            target_entity_id: Target entity UUID
            payload: Event payload (JSON-serializable)
            doctrine_section: Doctrine section reference
            
        Returns:
            Created SystemEvent
        """
        payload = payload or {}
        
        # Generate payload hash for integrity verification
        payload_hash = self.encryption_manager.hash_payload(payload)
        
        # Create event
        event = SystemEvent(
            project_id=project_id,
            actor_id=actor_id,
            actor_type=actor_type,
            actor_ip=actor_ip,
            actor_user_agent=actor_user_agent,
            event_type=event_type,
            severity=severity,
            action=action,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            payload=payload,
            payload_hash=payload_hash,
            doctrine_section=doctrine_section,
        )
        
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        
        return event
    
    async def log_validation_run(
        self,
        project_id: UUID,
        page_id: UUID,
        user_id: Optional[UUID],
        result: bool,
        blocks: List[Dict],
        warnings: List[Dict],
        doctrine_sections: List[str],
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
    ) -> SystemEvent:
        """Log validation run event"""
        return await self.create_event(
            event_type="VALIDATION_RUN",
            severity="BLOCK" if not result else "INFO",
            action="Preflight validation",
            project_id=project_id,
            actor_id=user_id,
            actor_type="user" if user_id else "system",
            actor_ip=actor_ip,
            actor_user_agent=actor_user_agent,
            target_entity_type="page",
            target_entity_id=page_id,
            payload={
                "page_id": str(page_id),
                "result": result,
                "blocks": blocks,
                "warnings": warnings,
                "doctrine_sections": doctrine_sections,
            },
            doctrine_section="Section 8: Preflight Validation",
        )
    
    async def log_generation_attempt(
        self,
        project_id: UUID,
        job_id: UUID,
        page_id: UUID,
        user_id: Optional[UUID],
        provider: str,
        model: str,
        tokens_estimated: Optional[int] = None,
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
    ) -> SystemEvent:
        """Log generation attempt event"""
        return await self.create_event(
            event_type="GENERATION_ATTEMPT",
            severity="INFO",
            action="AI content generation",
            project_id=project_id,
            actor_id=user_id,
            actor_type="user" if user_id else "system",
            actor_ip=actor_ip,
            actor_user_agent=actor_user_agent,
            target_entity_type="generation_job",
            target_entity_id=job_id,
            payload={
                "job_id": str(job_id),
                "page_id": str(page_id),
                "provider": provider,
                "model": model,
                "tokens_estimated": tokens_estimated,
            },
            doctrine_section="Section 8: AI Generation",
        )
    
    async def log_content_applied(
        self,
        project_id: UUID,
        job_id: UUID,
        page_id: UUID,
        user_id: UUID,
        faq_count: int,
        schema_generated: bool,
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
    ) -> SystemEvent:
        """Log content applied event"""
        return await self.create_event(
            event_type="CONTENT_APPLIED",
            severity="INFO",
            action="Content applied to page",
            project_id=project_id,
            actor_id=user_id,
            actor_type="user",
            actor_ip=actor_ip,
            actor_user_agent=actor_user_agent,
            target_entity_type="page",
            target_entity_id=page_id,
            payload={
                "job_id": str(job_id),
                "page_id": str(page_id),
                "faq_count": faq_count,
                "schema_generated": schema_generated,
            },
            doctrine_section="Section 8: Content Application",
        )
    
    async def log_page_published(
        self,
        project_id: UUID,
        page_id: UUID,
        user_id: UUID,
        validation_passed: bool,
        blocks_resolved: List[str],
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
    ) -> SystemEvent:
        """Log page published event"""
        return await self.create_event(
            event_type="PAGE_PUBLISHED",
            severity="INFO",
            action="Page published",
            project_id=project_id,
            actor_id=user_id,
            actor_type="user",
            actor_ip=actor_ip,
            actor_user_agent=actor_user_agent,
            target_entity_type="page",
            target_entity_id=page_id,
            payload={
                "page_id": str(page_id),
                "validation_passed": validation_passed,
                "blocks_resolved": blocks_resolved,
            },
            doctrine_section="Section 8: Publishing",
        )
    
    async def log_permission_change(
        self,
        project_id: UUID,
        target_user_id: UUID,
        old_role: str,
        new_role: str,
        changed_by: UUID,
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
    ) -> SystemEvent:
        """Log permission change event"""
        return await self.create_event(
            event_type="PERMISSION_CHANGE",
            severity="WARN",
            action="User role changed",
            project_id=project_id,
            actor_id=changed_by,
            actor_type="user",
            actor_ip=actor_ip,
            actor_user_agent=actor_user_agent,
            target_entity_type="user",
            target_entity_id=target_user_id,
            payload={
                "target_user_id": str(target_user_id),
                "old_role": old_role,
                "new_role": new_role,
                "changed_by": str(changed_by),
            },
            doctrine_section="Section 7: RBAC",
        )
    
    async def log_entitlement_check(
        self,
        project_id: UUID,
        user_id: UUID,
        feature: str,
        result: str,  # "granted" or "denied"
        plan: str,
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
    ) -> SystemEvent:
        """Log entitlement check event"""
        return await self.create_event(
            event_type="ENTITLEMENT_CHECK",
            severity="BLOCK" if result == "denied" else "INFO",
            action=f"Entitlement check: {feature}",
            project_id=project_id,
            actor_id=user_id,
            actor_type="user",
            actor_ip=actor_ip,
            actor_user_agent=actor_user_agent,
            target_entity_type="project",
            target_entity_id=project_id,
            payload={
                "feature": feature,
                "result": result,
                "plan": plan,
            },
            doctrine_section="Section 8: Entitlement Enforcement",
        )
    
    async def query_events(
        self,
        project_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        actor_id: Optional[UUID] = None,
        target_entity_type: Optional[str] = None,
        target_entity_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SystemEvent]:
        """
        Query audit events (read-only, immutable).
        
        Args:
            project_id: Filter by project
            event_type: Filter by event type
            severity: Filter by severity
            actor_id: Filter by actor
            target_entity_type: Filter by target entity type
            target_entity_id: Filter by target entity ID
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of SystemEvent records
        """
        stmt = select(SystemEvent)
        
        # Apply filters
        filters = []
        if project_id:
            filters.append(SystemEvent.project_id == project_id)
        if event_type:
            filters.append(SystemEvent.event_type == event_type)
        if severity:
            filters.append(SystemEvent.severity == severity)
        if actor_id:
            filters.append(SystemEvent.actor_id == actor_id)
        if target_entity_type:
            filters.append(SystemEvent.target_entity_type == target_entity_type)
        if target_entity_id:
            filters.append(SystemEvent.target_entity_id == target_entity_id)
        
        if filters:
            stmt = stmt.where(and_(*filters))
        
        # Order by created_at desc (newest first)
        stmt = stmt.order_by(desc(SystemEvent.created_at))
        
        # Limit and offset
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# Helper function to get audit logger
def get_audit_logger(db: AsyncSession) -> AuditLogger:
    """Get audit logger instance"""
    return AuditLogger(db)
