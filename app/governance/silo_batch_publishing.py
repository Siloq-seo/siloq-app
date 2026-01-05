"""
Silo Batch Publishing Logic

Strategy Update: The "Atomic Unit" of publishing is the SILO, not the page.

Rules:
- Don't Publish: When a Target Page is ready but blogs are still drafting
- Do Publish: When the entire cluster (Target + Supporting Pages) is "Finalized"
- Push them all simultaneously so they link instantly

Site Age Governor:
- Brand New Sites (<1 Year): Enforce a "Heartbeat Drip." Publish 1 Full Silo per Week (Safety mode)
- Established Sites (>1 Year): No speed limit. As soon as a Silo is finalized, push it live immediately
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.models import Site, Silo, Page, PageSilo, ContentStatus, SystemEvent
from app.governance.lifecycle_gates import LifecycleGateManager
from app.governance.silo_finalization import SiloFinalizer
from app.core.config import settings


class SiloBatchPublisher:
    """
    Handles batch publishing of entire silos.
    
    The atomic unit of publishing is the SILO (Target Page + all Supporting Pages).
    All pages in a finalized silo are published simultaneously to ensure instant linking.
    """
    
    def __init__(self):
        self.gate_manager = LifecycleGateManager()
        self.silo_finalizer = SiloFinalizer()
        self.HEARTBEAT_DRIP_INTERVAL_DAYS = 7  # 1 silo per week for new sites
    
    async def can_publish_silo(
        self,
        db: AsyncSession,
        silo_id: str,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Check if a silo can be published (batch publishing).
        
        Validates:
        - Silo is finalized
        - All pages in silo are ready (passed all gates)
        - Site age-based speed limit (heartbeat drip for new sites)
        
        Args:
            db: Database session
            silo_id: Silo identifier
            
        Returns:
            Tuple of (can_publish, blocking_reasons, details)
        """
        reasons = []
        details = {}
        
        silo = await db.get(Silo, silo_id)
        if not silo:
            return (False, ["Silo not found"], {})
        
        # Check 1: Silo must be finalized
        if not silo.is_finalized:
            reasons.append("Silo must be finalized before batch publishing")
            details["is_finalized"] = False
        else:
            details["is_finalized"] = True
            details["finalized_at"] = silo.finalized_at.isoformat() if silo.finalized_at else None
        
        # Check 2: Get all pages in silo
        pages = await self._get_silo_pages(db, silo_id)
        details["total_pages"] = len(pages)
        
        if not pages:
            reasons.append("Silo has no pages to publish")
            return (False, reasons, details)
        
        # Check 3: All pages must pass lifecycle gates
        pages_ready = []
        pages_not_ready = []
        
        for page in pages:
            gates_result = await self.gate_manager.check_all_gates(db, page)
            if gates_result["all_gates_passed"]:
                pages_ready.append(page)
            else:
                pages_not_ready.append({
                    "page_id": str(page.id),
                    "title": page.title,
                    "failed_gates": gates_result.get("failed_gates", []),
                    "reason": gates_result.get("reason", "Gates failed"),
                })
        
        details["pages_ready"] = len(pages_ready)
        details["pages_not_ready"] = len(pages_not_ready)
        details["pages_not_ready_details"] = pages_not_ready
        
        if pages_not_ready:
            reasons.append(
                f"{len(pages_not_ready)} page(s) have not passed all lifecycle gates"
            )
        
        # Check 4: Site age-based speed limit (heartbeat drip for new sites)
        site = await db.get(Site, silo.site_id)
        if site:
            site_age_days = (datetime.utcnow() - site.created_at).days if site.created_at else 0
            is_new_site = site_age_days < 365  # < 1 year
            
            details["site_age_days"] = site_age_days
            details["is_new_site"] = is_new_site
            
            if is_new_site:
                # Check heartbeat drip: Can only publish 1 silo per week
                last_published_silo = await self._get_last_published_silo_date(db, silo.site_id)
                
                if last_published_silo:
                    days_since_last = (datetime.utcnow() - last_published_silo).days
                    details["days_since_last_publish"] = days_since_last
                    
                    if days_since_last < self.HEARTBEAT_DRIP_INTERVAL_DAYS:
                        days_remaining = self.HEARTBEAT_DRIP_INTERVAL_DAYS - days_since_last
                        reasons.append(
                            f"New site (<1 year): Heartbeat drip enforced. "
                            f"Must wait {days_remaining} more day(s) before publishing next silo. "
                            f"(1 silo per week limit)"
                        )
                        details["heartbeat_drip_blocked"] = True
                    else:
                        details["heartbeat_drip_blocked"] = False
                else:
                    # No previous publish, allow first silo
                    details["heartbeat_drip_blocked"] = False
            else:
                # Established site: No speed limit
                details["heartbeat_drip_blocked"] = False
        
        can_publish = len(reasons) == 0
        return (can_publish, reasons, details)
    
    async def publish_silo_batch(
        self,
        db: AsyncSession,
        silo_id: str,
    ) -> Dict[str, Any]:
        """
        Publish entire silo as a batch (atomic unit).
        
        Publishes all pages in the silo simultaneously so they link instantly.
        
        Args:
            db: Database session
            silo_id: Silo identifier
            
        Returns:
            Publishing result with details
        """
        can_publish, reasons, details = await self.can_publish_silo(db, silo_id)
        
        if not can_publish:
            return {
                "success": False,
                "reason": "; ".join(reasons),
                "blocking_reasons": reasons,
                "details": details,
            }
        
        silo = await db.get(Silo, silo_id)
        if not silo:
            return {
                "success": False,
                "reason": "Silo not found",
            }
        
        # Get all pages in silo
        pages = await self._get_silo_pages(db, silo_id)
        
        # Publish all pages simultaneously
        published_pages = []
        failed_pages = []
        publish_timestamp = datetime.utcnow()
        
        for page in pages:
            try:
                # Double-check gates (safety check)
                gates_result = await self.gate_manager.check_all_gates(db, page)
                
                if not gates_result["all_gates_passed"]:
                    failed_pages.append({
                        "page_id": str(page.id),
                        "title": page.title,
                        "reason": gates_result.get("reason", "Gates failed"),
                    })
                    continue
                
                # Publish page
                page.status = ContentStatus.PUBLISHED
                page.published_at = publish_timestamp
                
                # Update governance_checks
                if not page.governance_checks:
                    page.governance_checks = {}
                page.governance_checks["published"] = {
                    "published_at": publish_timestamp.isoformat(),
                    "all_gates_passed": True,
                    "published_via": "silo_batch",
                    "silo_id": str(silo_id),
                }
                
                published_pages.append({
                    "page_id": str(page.id),
                    "title": page.title,
                    "path": page.path,
                })
                
            except Exception as e:
                failed_pages.append({
                    "page_id": str(page.id),
                    "title": page.title,
                    "reason": str(e),
                })
        
        # Commit all changes
        await db.commit()
        
        # Log batch publish event
        audit = SystemEvent(
            event_type="silo_batch_published",
            entity_type="silo",
            entity_id=silo_id,
            payload={
                "silo_id": str(silo_id),
                "published_at": publish_timestamp.isoformat(),
                "total_pages": len(pages),
                "published_count": len(published_pages),
                "failed_count": len(failed_pages),
                "published_pages": published_pages,
                "failed_pages": failed_pages,
            },
        )
        db.add(audit)
        await db.commit()
        
        return {
            "success": True,
            "silo_id": str(silo_id),
            "published_at": publish_timestamp.isoformat(),
            "total_pages": len(pages),
            "published_count": len(published_pages),
            "failed_count": len(failed_pages),
            "published_pages": published_pages,
            "failed_pages": failed_pages,
        }
    
    async def _get_silo_pages(
        self,
        db: AsyncSession,
        silo_id: str,
    ) -> List[Page]:
        """Get all pages in a silo."""
        query = (
            select(Page)
            .join(PageSilo, Page.id == PageSilo.page_id)
            .where(PageSilo.silo_id == silo_id)
        )
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def _get_last_published_silo_date(
        self,
        db: AsyncSession,
        site_id: str,
    ) -> Optional[datetime]:
        """
        Get the date when the last silo was published for this site.
        
        Used for heartbeat drip enforcement on new sites.
        """
        # Find the most recent published page in any silo for this site
        query = (
            select(Page.published_at)
            .join(PageSilo, Page.id == PageSilo.page_id)
            .join(Silo, PageSilo.silo_id == Silo.id)
            .where(
                and_(
                    Silo.site_id == site_id,
                    Page.status == ContentStatus.PUBLISHED,
                    Page.published_at.isnot(None),
                )
            )
            .order_by(Page.published_at.desc())
            .limit(1)
        )
        
        result = await db.execute(query)
        return result.scalar()
    
    async def get_silo_publish_status(
        self,
        db: AsyncSession,
        silo_id: str,
    ) -> Dict[str, Any]:
        """
        Get publishing status for a silo.
        
        Returns comprehensive status including:
        - Finalization status
        - Page readiness (gates passed)
        - Site age and speed limit status
        - Next available publish time (for new sites)
        """
        silo = await db.get(Silo, silo_id)
        if not silo:
            return {"error": "Silo not found"}
        
        can_publish, reasons, details = await self.can_publish_silo(db, silo_id)
        
        site = await db.get(Site, silo.site_id)
        site_age_days = (datetime.utcnow() - site.created_at).days if site and site.created_at else 0
        
        # Calculate next available publish time for new sites
        next_publish_time = None
        if site_age_days < 365:
            last_published = await self._get_last_published_silo_date(db, silo.site_id)
            if last_published:
                next_publish_time = last_published + timedelta(days=self.HEARTBEAT_DRIP_INTERVAL_DAYS)
            else:
                # No previous publish, can publish now
                next_publish_time = datetime.utcnow()
        
        return {
            "silo_id": str(silo_id),
            "is_finalized": silo.is_finalized,
            "finalized_at": silo.finalized_at.isoformat() if silo.finalized_at else None,
            "can_publish": can_publish,
            "blocking_reasons": reasons,
            "site_age_days": site_age_days,
            "is_new_site": site_age_days < 365,
            "speed_limit": "heartbeat_drip" if site_age_days < 365 else "none",
            "next_publish_time": next_publish_time.isoformat() if next_publish_time else None,
            "details": details,
        }

