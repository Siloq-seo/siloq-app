"""Event logging for decision engine - audit trail for all validation and state changes."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import SystemEvent
from app.decision.state_machine import StateTransition


class EventLogger:
    """
    Logs all validation attempts, state changes, and errors for audit trail.
    
    Provides comprehensive logging for:
    - Validation attempts and results
    - State transitions
    - Errors with error codes
    - System events
    """
    
    @staticmethod
    async def log_validation_attempt(
        db: AsyncSession,
        page_id: UUID,
        validation_result: Dict[str, Any],
        validator_type: str = "preflight",
    ) -> None:
        """
        Log a validation attempt.
        
        Args:
            db: Database session
            page_id: Page identifier
            validation_result: Validation result dictionary
            validator_type: Type of validator (e.g., "preflight")
        """
        event = SystemEvent(
            event_type=f"{validator_type}_validation",
            entity_type="pages",
            entity_id=page_id,
            payload={
                "validation_result": validation_result,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        db.add(event)
        await db.commit()
    
    @staticmethod
    async def log_state_transition(
        db: AsyncSession,
        job_id: UUID,
        transition: StateTransition,
    ) -> None:
        """
        Log a state transition.
        
        Args:
            db: Database session
            job_id: Job identifier
            transition: StateTransition instance
        """
        event = SystemEvent(
            event_type="state_transition",
            entity_type="generation_jobs",
            entity_id=job_id,
            payload=transition.to_dict(),
        )
        db.add(event)
        await db.commit()
    
    @staticmethod
    async def log_error(
        db: AsyncSession,
        entity_type: str,
        entity_id: UUID,
        error_code: str,
        error_details: Dict[str, Any],
    ) -> None:
        """
        Log an error with error code.
        
        Args:
            db: Database session
            entity_type: Type of entity (e.g., "pages", "generation_jobs")
            entity_id: Entity identifier
            error_code: Error code from ErrorCodeDictionary
            error_details: Additional error details
        """
        event = SystemEvent(
            event_type="error",
            entity_type=entity_type,
            entity_id=entity_id,
            payload={
                "error_code": error_code,
                "error_details": error_details,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        db.add(event)
        await db.commit()
    
    @staticmethod
    async def log_preflight_result(
        db: AsyncSession,
        page_id: UUID,
        passed: bool,
        errors: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        """
        Log preflight validation result.
        
        Args:
            db: Database session
            page_id: Page identifier
            passed: Whether validation passed
            errors: List of error dictionaries
            warnings: List of warning dictionaries
        """
        await EventLogger.log_validation_attempt(
            db,
            page_id,
            {
                "passed": passed,
                "errors": errors,
                "warnings": warnings,
                "validation_type": "preflight",
            },
            "preflight",
        )
    
    @staticmethod
    async def get_validation_history(
        db: AsyncSession,
        page_id: UUID,
        limit: int = 10,
    ) -> List[SystemEvent]:
        """
        Get validation history for a page.
        
        Args:
            db: Database session
            page_id: Page identifier
            limit: Maximum number of events to return
            
        Returns:
            List of SystemEvent instances
        """
        query = (
            select(SystemEvent)
            .where(
                SystemEvent.entity_type == "pages",
                SystemEvent.entity_id == page_id,
                SystemEvent.event_type.like("%validation"),
            )
            .order_by(SystemEvent.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_state_transition_history(
        db: AsyncSession,
        job_id: UUID,
        limit: int = 20,
    ) -> List[SystemEvent]:
        """
        Get state transition history for a job.
        
        Args:
            db: Database session
            job_id: Job identifier
            limit: Maximum number of events to return
            
        Returns:
            List of SystemEvent instances
        """
        query = (
            select(SystemEvent)
            .where(
                SystemEvent.entity_type == "generation_jobs",
                SystemEvent.entity_id == job_id,
                SystemEvent.event_type == "state_transition",
            )
            .order_by(SystemEvent.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())
