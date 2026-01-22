"""Week 6: Publishing safety checks and authority preservation with lifecycle gates"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Page, ContentStatus, SystemEvent
from app.governance.utils.page_helpers import is_safe_to_publish
from app.governance.lifecycle.redirect_manager import RedirectManager
from app.types import PublishingSafetyResult, AuthorityPreservationResult
from app.core.config import settings


class PublishingSafety:
    """Blocks unsafe publishing and preserves authority"""

    def __init__(self):
        # Lazy import to avoid circular dependency
        from app.governance.ai.ai_output import AIOutputGovernor
        self.governor = AIOutputGovernor()
        self.redirect_manager = RedirectManager()

    async def check_publishing_safety(
        self,
        db: AsyncSession,
        page: Page,
    ) -> PublishingSafetyResult:
        """
        Comprehensive safety check before allowing publication
        
        Returns:
            {
                "is_safe": bool,
                "checks": dict,
                "blocked": bool,
                "reason": str
            }
        """
        checks = {}
        blocked = False
        reason = ""

        # Check 1: Content must have passed all governance checks
        if not page.governance_checks:
            checks["governance_checks"] = {
                "passed": False,
                "message": "No governance checks performed",
            }
            blocked = True
            reason = "Content has not passed governance checks"
        else:
            all_passed = (
                page.governance_checks.get("pre_generation", {}).get("passed", False)
                and page.governance_checks.get("during_generation", {}).get("passed", False)
                and page.governance_checks.get("post_generation", {}).get("passed", False)
            )
            checks["governance_checks"] = {
                "passed": all_passed,
                "details": page.governance_checks,
            }
            if not all_passed:
                blocked = True
                reason = "Content failed one or more governance checks"

        # Check 2: Content must have embedding for cannibalization tracking
        if not page.embedding:
            checks["embedding"] = {
                "passed": False,
                "message": "Content must have vector embedding",
            }
            blocked = True
            reason = "Content missing vector embedding for cannibalization tracking"

        # Check 3: Authority preservation
        if page.authority_score > settings.authority_threshold_for_sources:
            if not page.source_urls or len(page.source_urls) == 0:
                checks["authority_sources"] = {
                    "passed": False,
                    "message": "High authority content requires source URLs",
                }
                blocked = True
                reason = "Authority preservation failed: missing source URLs"

        # Check 4: Content structure validation
        if not page.title or len(page.title.strip()) < settings.min_title_length:
            checks["title"] = {
                "passed": False,
                "message": f"Title must be at least {settings.min_title_length} characters",
            }
            blocked = True
            reason = "Title structure invalid"

        if not page.body or len(page.body.strip()) < settings.min_body_length:
            checks["body"] = {
                "passed": False,
                "message": f"Body must be at least {settings.min_body_length} characters",
            }
            blocked = True
            reason = "Body content insufficient"

        # Check 5: Status validation
        if page.status not in [ContentStatus.APPROVED, ContentStatus.DRAFT]:
            if page.status == ContentStatus.BLOCKED:
                checks["status"] = {
                    "passed": False,
                    "message": "Content is blocked from publishing",
                }
                blocked = True
                reason = "Content status is BLOCKED"
            elif page.status == ContentStatus.DECOMMISSIONED:
                checks["status"] = {
                    "passed": False,
                    "message": "Decommissioned content cannot be published",
                }
                blocked = True
                reason = "Cannot publish decommissioned content"

        is_safe_result = not blocked and all(
            check.get("passed", False) for check in checks.values()
        )

        # Store safety checks in governance_checks
        if not page.governance_checks:
            page.governance_checks = {}
        page.governance_checks["safety_check"] = {
            "is_safe": is_safe_result,
            "checks": checks,
            "blocked": blocked,
            "reason": reason,
        }

        # Record audit using SystemEvent
        audit = SystemEvent(
            event_type="publishing_safety_check",
            entity_type="page",
            entity_id=page.id,
            payload={
                "is_safe": is_safe_result,
                "blocked": blocked,
                "checks": checks,
                "reason": reason,
            },
        )
        db.add(audit)

        return {
            "is_safe": is_safe_result,
            "checks": checks,
            "blocked": blocked,
            "reason": reason,
        }

    async def preserve_authority_on_decommission(
        self,
        db: AsyncSession,
        page: Page,
        redirect_to: Optional[str] = None,
    ) -> AuthorityPreservationResult:
        """
        Week 6: Preserve authority when decommissioning content with redirect enforcement.
        
        This ensures that:
        - Source URLs are preserved
        - Authority score is maintained
        - Redirects are validated and enforced
        - Historical records are kept
        """
        # Week 6: Validate and enforce redirect
        redirect_result = await self.redirect_manager.enforce_redirect(
            db, page, redirect_to
        )
        
        if not redirect_result["success"]:
            return {
                "success": False,
                "authority_preserved": False,
                "error": redirect_result.get("error", "Redirect validation failed"),
                "redirect_result": redirect_result,
            }
        
        # Update status
        if page.status != ContentStatus.DECOMMISSIONED:
            page.status = ContentStatus.DECOMMISSIONED
            page.decommissioned_at = datetime.utcnow()

        # Preserve authority data
        authority_data = {
            "original_authority_score": page.authority_score,
            "source_urls": page.source_urls,
            "decommissioned_at": page.decommissioned_at.isoformat() if page.decommissioned_at else None,
            "redirect_to": redirect_to,
            "redirect_enforced": redirect_result.get("redirect_enforced", False),
            "is_internal_redirect": redirect_result.get("is_internal", False),
            "target_page_id": str(redirect_result.get("target_page_id")) if redirect_result.get("target_page_id") else None,
        }

        # Store in governance checks for historical reference
        if not page.governance_checks:
            page.governance_checks = {}
        page.governance_checks["decommission"] = authority_data

        # Record audit using SystemEvent
        audit = SystemEvent(
            event_type="authority_preserved_on_decommission",
            entity_type="page",
            entity_id=page.id,
            payload=authority_data,
        )
        db.add(audit)

        await db.commit()

        return {
            "success": True,
            "authority_preserved": True,
            "authority_data": authority_data,
            "redirect_enforced": redirect_result.get("redirect_enforced", False),
        }

    async def block_unsafe_content(
        self,
        db: AsyncSession,
        page: Page,
        reason: str,
    ) -> Dict[str, Any]:
        """Explicitly block content from publishing"""
        page.status = ContentStatus.BLOCKED

        # Store blocked status in governance_checks
        if not page.governance_checks:
            page.governance_checks = {}
        if "safety_check" not in page.governance_checks:
            page.governance_checks["safety_check"] = {}
        page.governance_checks["safety_check"]["blocked"] = {
            "blocked_at": datetime.utcnow().isoformat(),
            "reason": reason,
        }

        # Record audit using SystemEvent
        audit = SystemEvent(
            event_type="content_blocked",
            entity_type="page",
            entity_id=page.id,
            payload={"reason": reason},
        )
        db.add(audit)

        await db.commit()

        return {
            "success": True,
            "blocked": True,
            "reason": reason,
        }

