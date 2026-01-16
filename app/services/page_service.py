"""
Page Service - Business logic for page operations.

This service layer handles page-related business logic, separating it from
HTTP concerns in the API routes. Routes should call service methods rather
than directly accessing governance modules.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Page, ContentStatus, GenerationJob, SystemEvent
from app.governance.lifecycle_gates import LifecycleGateManager
from app.governance.publishing import PublishingSafety
from app.exceptions import LifecycleGateError, PublishingError, DecommissionError
from app.decision.error_codes import ErrorCodeDictionary
from app.types import AllGatesResult, AuthorityPreservationResult


class PageService:
    """
    Service for page-related business operations.
    
    This service encapsulates business logic for pages, including:
    - Publishing workflow
    - Decommissioning workflow
    - Gate checking
    - State management
    """
    
    def __init__(
        self,
        gate_manager: Optional[LifecycleGateManager] = None,
        publishing_safety: Optional[PublishingSafety] = None,
    ):
        """
        Initialize page service.
        
        Args:
            gate_manager: Lifecycle gate manager (created if not provided)
            publishing_safety: Publishing safety service (created if not provided)
        """
        self.gate_manager = gate_manager or LifecycleGateManager()
        self.publishing_safety = publishing_safety or PublishingSafety()
    
    async def check_publish_gates(
        self,
        db: AsyncSession,
        page_id: UUID,
    ) -> AllGatesResult:
        """
        Check all lifecycle gates for a page.
        
        Args:
            db: Database session
            page_id: Page UUID
            
        Returns:
            Gate check results
            
        Raises:
            ValueError: If page not found
        """
        page = await db.get(Page, page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")
        
        return await self.gate_manager.check_all_gates(db, page)
    
    async def publish_page(
        self,
        db: AsyncSession,
        page_id: UUID,
    ) -> dict:
        """
        Publish a page after checking all lifecycle gates.
        
        Args:
            db: Database session
            page_id: Page UUID
            
        Returns:
            Success response with published_at timestamp
            
        Raises:
            LifecycleGateError: If any gate fails
            ValueError: If page not found
        """
        page = await db.get(Page, page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")
        
        # Check all lifecycle gates
        gates_result = await self.gate_manager.check_all_gates(db, page)
        
        if not gates_result["all_gates_passed"]:
            failed_gates = gates_result.get("failed_gates", [])
            error_code = None
            
            if "governance" in failed_gates:
                error_code = ErrorCodeDictionary.LIFECYCLE_001
            elif "schema_sync" in failed_gates:
                error_code = ErrorCodeDictionary.LIFECYCLE_002
            elif "embedding" in failed_gates:
                error_code = ErrorCodeDictionary.LIFECYCLE_003
            elif "authority" in failed_gates:
                error_code = ErrorCodeDictionary.LIFECYCLE_004
            elif "structure" in failed_gates:
                error_code = ErrorCodeDictionary.LIFECYCLE_005
            elif "status" in failed_gates:
                error_code = ErrorCodeDictionary.LIFECYCLE_006
            
            raise LifecycleGateError(
                error_code=error_code or ErrorCodeDictionary.LIFECYCLE_001,
                entity_id=page_id,
                context={
                    "gates": gates_result.get("gates", {}),
                    "failed_gates": failed_gates,
                },
            )
        
        # All gates passed - publish
        page.status = ContentStatus.PUBLISHED
        page.published_at = datetime.utcnow()
        
        # Update governance_checks with publish info
        if not page.governance_checks:
            page.governance_checks = {}
        page.governance_checks["published"] = {
            "published_at": page.published_at.isoformat(),
            "all_gates_passed": True,
        }
        
        # Log publish event
        audit = SystemEvent(
            event_type="page_published",
            entity_type="page",
            entity_id=page.id,
            payload={
                "published_at": page.published_at.isoformat(),
                "all_gates_passed": True,
                "gates": gates_result.get("gates", {}),
            },
        )
        db.add(audit)
        
        await db.commit()
        
        return {
            "success": True,
            "page_id": str(page_id),
            "status": "published",
            "published_at": page.published_at.isoformat(),
            "all_gates_passed": True,
        }
    
    async def decommission_page(
        self,
        db: AsyncSession,
        page_id: UUID,
        redirect_to: Optional[str] = None,
    ) -> AuthorityPreservationResult:
        """
        Decommission a page while preserving authority.
        
        Args:
            db: Database session
            page_id: Page UUID
            redirect_to: Optional redirect URL
            
        Returns:
            Authority preservation result
            
        Raises:
            DecommissionError: If redirect validation fails
            ValueError: If page not found
        """
        page = await db.get(Page, page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")
        
        result = await self.publishing_safety.preserve_authority_on_decommission(
            db, page, redirect_to
        )
        
        if not result.get("success"):
            error_code = ErrorCodeDictionary.LIFECYCLE_007
            raise DecommissionError(
                error_code=error_code,
                entity_id=page_id,
                context={"redirect_result": result},
            )
        
        return result

