"""AI output governance before, during, and after generation"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from app.db.models import Page, GenerationJob, Silo, SystemEvent
from app.governance.content.cannibalization import CannibalizationDetector
from app.governance.structure.reverse_silos import ReverseSiloEnforcer
from app.governance.utils.page_helpers import get_page_silo_id, get_page_slug
from app.core.config import settings


class AIOutputGovernor:
    """Governs AI output at all stages of generation"""

    def __init__(self):
        self.cannibalization_detector = CannibalizationDetector()
        self.silo_enforcer = ReverseSiloEnforcer()

    async def pre_generation_checks(
        self,
        db: AsyncSession,
        page: Page,
        proposed_embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Governance checks BEFORE AI generation
        
        Returns:
            {
                "passed": bool,
                "checks": dict,
                "blocked": bool,
                "reason": str
            }
        """
        checks = {}
        blocked = False
        reason = ""

        # Check 1: Reverse Silos structure
        silo_id = get_page_silo_id(page)
        if silo_id:
            silo_query = select(Silo).where(Silo.id == silo_id)
            silo_result = await db.execute(silo_query)
            silo = silo_result.scalar_one_or_none()
            
            if silo:
                is_valid, message = await self.silo_enforcer.validate_silo_structure(
                    db, str(page.site_id)
                )
                checks["silo_structure"] = {
                    "passed": is_valid,
                    "message": message,
                }
                if not is_valid:
                    blocked = True
                    reason = f"Silo structure invalid: {message}"

        # Check 2: Cannibalization (if embedding available)
        if proposed_embedding:
            cannibalization_result = await self.cannibalization_detector.check_cannibalization(
                db,
                page.id,
                proposed_embedding,
                page.site_id,
            )
            checks["cannibalization"] = {
                "passed": not cannibalization_result["is_cannibalized"],
                "similarity": cannibalization_result["max_similarity"],
                "similar_content": cannibalization_result["similar_content"],
            }
            if cannibalization_result["is_cannibalized"]:
                blocked = True
                reason = f"Content would cannibalize existing content (similarity: {cannibalization_result['max_similarity']:.2f})"

        # Check 3: Content structure validation
        if not page.title or len(page.title.strip()) < settings.min_title_length:
            checks["title_structure"] = {
                "passed": False,
                "message": f"Title must be at least {settings.min_title_length} characters",
            }
            blocked = True
            reason = "Title structure invalid"

        slug = get_page_slug(page)
        if not slug or len(slug.strip()) < settings.min_slug_length:
            checks["slug_structure"] = {
                "passed": False,
                "message": f"Slug must be at least {settings.min_slug_length} characters",
            }
            blocked = True
            reason = "Slug structure invalid"

        passed = not blocked and all(
            check.get("passed", False) for check in checks.values()
        )

        # Record audit using SystemEvent
        audit = SystemEvent(
            event_type="pre_generation_check",
            entity_type="page",
            entity_id=page.id,
            payload={
                "passed": passed,
                "blocked": blocked,
                "checks": checks,
                "reason": reason,
            },
        )
        db.add(audit)

        return {
            "passed": passed,
            "checks": checks,
            "blocked": blocked,
            "reason": reason,
        }

    async def during_generation_checks(
        self,
        db: AsyncSession,
        page: Page,
        generation_output: str,
    ) -> Dict[str, Any]:
        """
        Governance checks DURING AI generation
        
        Returns:
            {
                "passed": bool,
                "checks": dict,
                "blocked": bool,
                "reason": str
            }
        """
        checks = {}
        blocked = False
        reason = ""

        # Check 1: Output length constraints
        min_length = 500
        max_length = 50000
        output_length = len(generation_output)

        checks["length"] = {
            "passed": min_length <= output_length <= max_length,
            "length": output_length,
            "min": min_length,
            "max": max_length,
        }

        if not checks["length"]["passed"]:
            blocked = True
            reason = f"Output length {output_length} outside valid range ({min_length}-{max_length})"

        # Check 2: Content quality indicators
        # Check for minimum sentence count
        sentences = generation_output.split(".")
        sentence_count = len([s for s in sentences if len(s.strip()) > 10])

        checks["sentence_structure"] = {
            "passed": sentence_count >= 5,
            "sentence_count": sentence_count,
        }

        if not checks["sentence_structure"]["passed"]:
            blocked = True
            reason = f"Insufficient sentence structure (found {sentence_count} sentences, minimum 5)"

        # Check 3: Intent preservation (basic keyword presence)
        # This would be more sophisticated in production
        if page.title:
            title_keywords = set(page.title.lower().split())
            output_lower = generation_output.lower()
            keyword_presence = sum(1 for kw in title_keywords if kw in output_lower)
            keyword_ratio = keyword_presence / len(title_keywords) if title_keywords else 0

            checks["intent_preservation"] = {
                "passed": keyword_ratio >= 0.3,
                "keyword_ratio": keyword_ratio,
            }

            if not checks["intent_preservation"]["passed"]:
                blocked = True
                reason = f"Intent not preserved (keyword ratio: {keyword_ratio:.2f}, minimum 0.3)"

        passed = not blocked and all(
            check.get("passed", False) for check in checks.values()
        )

        # Record audit using SystemEvent
        audit = SystemEvent(
            event_type="during_generation_check",
            entity_type="page",
            entity_id=page.id,
            payload={
                "passed": passed,
                "blocked": blocked,
                "checks": checks,
                "reason": reason,
            },
        )
        db.add(audit)

        return {
            "passed": passed,
            "checks": checks,
            "blocked": blocked,
            "reason": reason,
        }

    async def post_generation_checks(
        self,
        db: AsyncSession,
        page: Page,
        final_embedding: List[float],
    ) -> Dict[str, Any]:
        """
        Governance checks AFTER AI generation
        
        Returns:
            {
                "passed": bool,
                "checks": dict,
                "blocked": bool,
                "reason": str
            }
        """
        checks = {}
        blocked = False
        reason = ""

        # Check 1: Final cannibalization check with actual embedding
        cannibalization_result = await self.cannibalization_detector.check_cannibalization(
            db,
            str(page.id),
            final_embedding,
            str(page.site_id),
        )

        checks["final_cannibalization"] = {
            "passed": not cannibalization_result["is_cannibalized"],
            "similarity": cannibalization_result["max_similarity"],
            "similar_content": cannibalization_result["similar_content"],
        }

        if cannibalization_result["is_cannibalized"]:
            blocked = True
            reason = f"Final content cannibalizes existing content (similarity: {cannibalization_result['max_similarity']:.2f})"

        # Check 2: Authority preservation
        # Ensure source URLs are present if authority score is high
        if page.authority_score > 0.7 and not page.source_urls:
            checks["authority_preservation"] = {
                "passed": False,
                "message": "High authority score requires source URLs",
            }
            blocked = True
            reason = "Authority preservation failed: missing source URLs"

        # Check 3: Content completeness
        missing_fields = []
        if not page.title:
            missing_fields.append("title")
        if not get_page_slug(page):
            missing_fields.append("slug")
        if not page.body:
            missing_fields.append("body")

        checks["completeness"] = {
            "passed": len(missing_fields) == 0,
            "missing_fields": missing_fields,
        }

        if missing_fields:
            blocked = True
            reason = f"Content incomplete: missing {', '.join(missing_fields)}"

        passed = not blocked and all(
            check.get("passed", False) for check in checks.values()
        )

        # Record audit using SystemEvent
        audit = SystemEvent(
            event_type="post_generation_check",
            entity_type="page",
            entity_id=page.id,
            payload={
                "passed": passed,
                "blocked": blocked,
                "checks": checks,
                "reason": reason,
            },
        )
        db.add(audit)

        return {
            "passed": passed,
            "checks": checks,
            "blocked": blocked,
            "reason": reason,
        }

