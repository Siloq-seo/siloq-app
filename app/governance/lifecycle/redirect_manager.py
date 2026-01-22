"""Week 6: Redirect Manager - Enforces redirects on decommission."""
from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from uuid import UUID

from app.db.models import Page, SystemEvent, ContentStatus
from app.decision.error_codes import ErrorCodeDictionary
from app.types import RedirectValidationResult, RedirectEnforcementResult


class RedirectManager:
    """
    Week 6: Manages redirects when decommissioning pages.
    
    Ensures:
    - Redirect URLs are valid
    - Redirect targets exist (if internal)
    - Redirects are logged for audit
    - Authority is preserved through redirects
    """
    
    async def validate_redirect(
        self,
        db: AsyncSession,
        page: Page,
        redirect_to: Optional[str],
    ) -> RedirectValidationResult:
        """
        Validate redirect URL.
        
        Args:
            db: Database session
            page: Page being decommissioned
            redirect_to: Redirect URL (can be internal path or external URL)
            
        Returns:
            {
                "valid": bool,
                "is_internal": bool,
                "target_page_id": Optional[UUID],
                "issues": List[str]
            }
        """
        if not redirect_to:
            return {
                "valid": True,  # No redirect is valid
                "is_internal": False,
                "target_page_id": None,
                "issues": [],
            }
        
        issues = []
        is_internal = False
        target_page_id = None
        
        # Check if it's an internal path (starts with /)
        if redirect_to.startswith("/"):
            is_internal = True
            
            # Find target page by path
            from app.db.models import Site
            site = await db.get(Site, page.site_id)
            if not site:
                issues.append("Site not found")
            else:
                # Normalize path for lookup
                normalized_redirect = redirect_to.lower().strip()
                
            # Query for page with matching path (case-insensitive)
            # Note: We compare against normalized_path in the database
            query = select(Page).where(
                and_(
                    Page.site_id == page.site_id,
                    # Use LOWER and TRIM to match normalized_path behavior
                    func.lower(func.trim(Page.path)) == normalized_redirect,
                    Page.status == ContentStatus.PUBLISHED,  # Target must be published
                )
            )
            result = await db.execute(query)
            target_page = result.scalar_one_or_none()
            
            if not target_page:
                issues.append(f"Target page not found at path: {redirect_to}")
            else:
                target_page_id = target_page.id
                
                # Check target is not the same page
                if target_page.id == page.id:
                    issues.append("Cannot redirect to self")
        else:
            # External URL - validate format
            from urllib.parse import urlparse
            parsed = urlparse(redirect_to)
            if not parsed.scheme or not parsed.netloc:
                issues.append(f"Invalid external URL format: {redirect_to}")
        
        return {
            "valid": len(issues) == 0,
            "is_internal": is_internal,
            "target_page_id": target_page_id,
            "issues": issues,
        }
    
    async def enforce_redirect(
        self,
        db: AsyncSession,
        page: Page,
        redirect_to: Optional[str],
    ) -> RedirectEnforcementResult:
        """
        Enforce redirect on decommission.
        
        This:
        1. Validates redirect URL
        2. Stores redirect in governance_checks
        3. Logs redirect for audit
        4. Returns redirect information
        
        Args:
            db: Database session
            page: Page being decommissioned
            redirect_to: Redirect URL
            
        Returns:
            {
                "success": bool,
                "redirect_enforced": bool,
                "redirect_to": Optional[str],
                "is_internal": bool,
                "target_page_id": Optional[UUID],
                "error": Optional[str]
            }
        """
        if not redirect_to:
            return {
                "success": True,
                "redirect_enforced": False,
                "redirect_to": None,
                "is_internal": False,
                "target_page_id": None,
            }
        
        # Validate redirect
        validation = await self.validate_redirect(db, page, redirect_to)
        
        if not validation["valid"]:
            return {
                "success": False,
                "redirect_enforced": False,
                "redirect_to": redirect_to,
                "error": f"Invalid redirect: {', '.join(validation['issues'])}",
            }
        
        # Store redirect in governance_checks
        if not page.governance_checks:
            page.governance_checks = {}
        
        if "decommission" not in page.governance_checks:
            page.governance_checks["decommission"] = {}
        
        page.governance_checks["decommission"]["redirect"] = {
            "redirect_to": redirect_to,
            "is_internal": validation["is_internal"],
            "target_page_id": str(validation["target_page_id"]) if validation["target_page_id"] else None,
            "enforced_at": datetime.utcnow().isoformat(),
        }
        
        # Log redirect enforcement
        audit = SystemEvent(
            event_type="redirect_enforced",
            entity_type="page",
            entity_id=page.id,
            payload={
                "redirect_to": redirect_to,
                "is_internal": validation["is_internal"],
                "target_page_id": str(validation["target_page_id"]) if validation["target_page_id"] else None,
                "from_path": page.path,
            },
        )
        db.add(audit)
        
        return {
            "success": True,
            "redirect_enforced": True,
            "redirect_to": redirect_to,
            "is_internal": validation["is_internal"],
            "target_page_id": validation["target_page_id"],
        }

