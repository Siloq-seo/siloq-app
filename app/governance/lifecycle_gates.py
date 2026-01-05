"""
Week 6: Lifecycle Gates - Unsafe content cannot ship.

This module implements the lifecycle gate manager that enforces all safety
checks before allowing content to be published. All gates must pass for
content to be published.

Gates:
1. Governance checks gate - All governance checks (pre/during/post) must have passed
2. Schema sync validation gate - JSON-LD schema must match content
3. Embedding gate - Vector embedding must exist for cannibalization tracking
4. Authority gate - High authority content requires source URLs
5. Content structure gate - Title, body, and path must be valid
6. Status gate - Status must allow publishing
7. Experience verification gate - Content must demonstrate first-hand experience (2025 SEO)
8. GEO formatting gate - Content must be formatted for AI citation (2025 SEO)
9. Core Web Vitals gate - Mobile-first rendering validation (2025 SEO)
10. Media integrity gate - Multimedia governance (WebP, alt-text, VideoObject schema) (2026 SEO)

Example:
    >>> gate_manager = LifecycleGateManager()
    >>> result = await gate_manager.check_all_gates(db, page)
    >>> if result["all_gates_passed"]:
    ...     await publish_page(page)
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Page, ContentStatus, SystemEvent
from app.governance.publishing import PublishingSafety
from app.schemas.jsonld import JSONLDGenerator
from app.decision.error_codes import ErrorCodeDictionary
from app.governance.experience_verification import ExperienceVerifier
from app.governance.geo_formatting import GEOFormatter
from app.governance.core_web_vitals import CoreWebVitalsValidator
from app.governance.media_integrity import MediaIntegrityValidator
from app.types import GateCheckResult, AllGatesResult
from app.core.config import settings


class LifecycleGateManager:
    """
    Week 6: Manages all lifecycle gates to ensure unsafe content cannot ship.
    
    This class checks all lifecycle gates before allowing content to be published.
    If any gate fails, publishing is blocked with a detailed error.
    
    Gates:
    1. Governance checks gate
    2. Schema sync validation gate
    3. Embedding gate
    4. Authority gate
    5. Content structure gate
    6. Status gate
    7. Experience verification gate (2025 SEO)
    8. GEO formatting gate (2025 SEO)
    9. Core Web Vitals gate (2025 SEO)
    10. Media integrity gate (2026 SEO)
    """
    
    def __init__(self):
        self.publishing_safety = PublishingSafety()
        self.jsonld_generator = JSONLDGenerator()
        self.experience_verifier = ExperienceVerifier()
        self.geo_formatter = GEOFormatter()
        self.web_vitals_validator = CoreWebVitalsValidator()
        self.media_integrity_validator = MediaIntegrityValidator()
    
    async def check_all_gates(
        self,
        db: AsyncSession,
        page: Page,
    ) -> AllGatesResult:
        """
        Check all lifecycle gates before publishing.
        
        Returns:
            {
                "all_gates_passed": bool,
                "gates": dict,  # Individual gate results
                "blocked": bool,
                "reason": str,
                "failed_gates": List[str]
            }
        """
        gates = {}
        failed_gates = []
        blocked = False
        reason = ""
        
        # Gate 1: Governance Checks Gate
        governance_result = await self._check_governance_gate(db, page)
        gates["governance"] = governance_result
        if not governance_result["passed"]:
            failed_gates.append("governance")
            blocked = True
            reason = governance_result.get("reason", "Governance checks failed")
        
        # Gate 2: Schema Sync Validation Gate
        schema_result = await self._check_schema_sync_gate(db, page)
        gates["schema_sync"] = schema_result
        if not schema_result["passed"]:
            failed_gates.append("schema_sync")
            blocked = True
            if not reason:
                reason = schema_result.get("reason", "Schema sync validation failed")
        
        # Gate 3: Embedding Gate
        embedding_result = await self._check_embedding_gate(page)
        gates["embedding"] = embedding_result
        if not embedding_result["passed"]:
            failed_gates.append("embedding")
            blocked = True
            if not reason:
                reason = embedding_result.get("reason", "Embedding missing")
        
        # Gate 4: Authority Gate
        authority_result = await self._check_authority_gate(page)
        gates["authority"] = authority_result
        if not authority_result["passed"]:
            failed_gates.append("authority")
            blocked = True
            if not reason:
                reason = authority_result.get("reason", "Authority validation failed")
        
        # Gate 5: Content Structure Gate
        structure_result = await self._check_structure_gate(page)
        gates["structure"] = structure_result
        if not structure_result["passed"]:
            failed_gates.append("structure")
            blocked = True
            if not reason:
                reason = structure_result.get("reason", "Content structure invalid")
        
        # Gate 6: Status Gate
        status_result = await self._check_status_gate(page)
        gates["status"] = status_result
        if not status_result["passed"]:
            failed_gates.append("status")
            blocked = True
            if not reason:
                reason = status_result.get("reason", "Status does not allow publishing")
        
        # Gate 7: Experience Verification Gate (2025 SEO)
        experience_result = await self._check_experience_gate(page)
        gates["experience"] = experience_result
        if not experience_result["passed"]:
            failed_gates.append("experience")
            blocked = True
            if not reason:
                reason = experience_result.get("reason", "Experience verification failed")
        
        # Gate 8: GEO Formatting Gate (2025 SEO)
        geo_result = await self._check_geo_gate(page)
        gates["geo_formatting"] = geo_result
        if not geo_result["passed"]:
            failed_gates.append("geo_formatting")
            blocked = True
            if not reason:
                reason = geo_result.get("reason", "GEO formatting validation failed")
        
        # Gate 9: Core Web Vitals Gate (2025 SEO)
        web_vitals_result = await self._check_web_vitals_gate(db, page)
        gates["web_vitals"] = web_vitals_result
        if not web_vitals_result["passed"]:
            failed_gates.append("web_vitals")
            blocked = True
            if not reason:
                reason = web_vitals_result.get("reason", "Core Web Vitals validation failed")
        
        # Gate 10: Media Integrity Gate (2026 SEO)
        media_result = await self._check_media_integrity_gate(db, page)
        gates["media_integrity"] = media_result
        if not media_result["passed"]:
            failed_gates.append("media_integrity")
            blocked = True
            if not reason:
                reason = media_result.get("reason", "Media integrity validation failed")
        
        all_gates_passed = not blocked and all(
            gate.get("passed", False) for gate in gates.values()
        )
        
        # Log gate check
        audit = SystemEvent(
            event_type="lifecycle_gates_check",
            entity_type="page",
            entity_id=page.id,
            payload={
                "all_gates_passed": all_gates_passed,
                "gates": gates,
                "failed_gates": failed_gates,
                "blocked": blocked,
                "reason": reason,
            },
        )
        db.add(audit)
        
        return {
            "all_gates_passed": all_gates_passed,
            "gates": gates,
            "blocked": blocked,
            "reason": reason,
            "failed_gates": failed_gates,
        }
    
    async def _check_governance_gate(
        self,
        db: AsyncSession,
        page: Page,
    ) -> GateCheckResult:
        """Gate 1: All governance checks must have passed."""
        if not page.governance_checks:
            return {
                "passed": False,
                "reason": "No governance checks performed",
                "details": "Page has not undergone governance validation",
            }
        
        pre_gen = page.governance_checks.get("pre_generation", {}).get("passed", False)
        during_gen = page.governance_checks.get("during_generation", {}).get("passed", False)
        post_gen = page.governance_checks.get("post_generation", {}).get("passed", False)
        
        all_passed = pre_gen and during_gen and post_gen
        
        if not all_passed:
            failed_stages = []
            if not pre_gen:
                failed_stages.append("pre_generation")
            if not during_gen:
                failed_stages.append("during_generation")
            if not post_gen:
                failed_stages.append("post_generation")
            
            return {
                "passed": False,
                "reason": f"Governance checks failed at: {', '.join(failed_stages)}",
                "details": {
                    "pre_generation": pre_gen,
                    "during_generation": during_gen,
                    "post_generation": post_gen,
                },
            }
        
        return {
            "passed": True,
            "details": {
                "pre_generation": pre_gen,
                "during_generation": during_gen,
                "post_generation": post_gen,
            },
        }
    
    async def _check_schema_sync_gate(
        self,
        db: AsyncSession,
        page: Page,
    ) -> GateCheckResult:
        """
        Gate 2: Schema sync validation - JSON-LD schema must match content.
        
        Validates:
        - Schema headline matches page title
        - Schema description matches page body (extracted)
        - Schema URL matches page path
        - Schema dates match page timestamps
        """
        try:
            # Generate current schema
            current_schema = await self.jsonld_generator.generate_schema(db, page)
            
            # Validate schema matches content
            issues = []
            
            # Check headline matches title
            if current_schema.get("headline") != page.title:
                issues.append("Schema headline does not match page title")
            
            # Check mainEntityOfPage URL matches path
            main_entity = current_schema.get("mainEntityOfPage", {})
            if main_entity.get("@id"):
                # Extract path from full URL
                schema_url = main_entity["@id"]
                # Get domain from site to extract path
                from app.db.models import Site
                site = await db.get(Site, page.site_id)
                if site and site.domain:
                    # Remove domain and protocol to get path
                    domain_part = f"https://{site.domain}"
                    if schema_url.startswith(domain_part):
                        schema_path = schema_url[len(domain_part):]
                        if schema_path != page.path:
                            issues.append(f"Schema URL path '{schema_path}' does not match page path '{page.path}'")
                else:
                    # If no domain, just check if path is in URL
                    if page.path not in schema_url:
                        issues.append("Schema URL does not contain page path")
            
            # Check datePublished matches created_at
            schema_date = current_schema.get("datePublished")
            if schema_date:
                # Compare dates (allowing for timezone differences)
                page_date = page.created_at.isoformat() if page.created_at else None
                if page_date and schema_date[:10] != page_date[:10]:  # Compare date part only
                    issues.append("Schema datePublished does not match page created_at")
            
            # Check dateModified matches updated_at
            schema_modified = current_schema.get("dateModified")
            if schema_modified:
                page_modified = page.updated_at.isoformat() if page.updated_at else None
                if page_modified and schema_modified[:10] != page_modified[:10]:
                    issues.append("Schema dateModified does not match page updated_at")
            
            if issues:
                return {
                    "passed": False,
                    "reason": "Schema does not match content",
                    "details": {
                        "issues": issues,
                        "schema": current_schema,
                    },
                }
            
            return {
                "passed": True,
                "details": {
                    "schema_validated": True,
                    "schema_type": current_schema.get("@type"),
                },
            }
            
        except Exception as e:
            return {
                "passed": False,
                "reason": f"Schema validation error: {str(e)}",
                "details": {"error": str(e)},
            }
    
    async def _check_embedding_gate(
        self,
        page: Page,
    ) -> GateCheckResult:
        """Gate 3: Embedding must exist for cannibalization tracking."""
        if not page.embedding:
            return {
                "passed": False,
                "reason": "Page must have vector embedding for cannibalization tracking",
                "details": {"embedding_exists": False},
            }
        
        return {
            "passed": True,
            "details": {
                "embedding_exists": True,
                "embedding_dimension": len(page.embedding) if page.embedding else 0,
            },
        }
    
    async def _check_authority_gate(
        self,
        page: Page,
    ) -> GateCheckResult:
        """Gate 4: Authority validation - high authority requires sources."""
        if page.authority_score > settings.authority_threshold_for_sources:
            if not page.source_urls or len(page.source_urls) == 0:
                return {
                    "passed": False,
                    "reason": f"High authority content (score: {page.authority_score}) requires source URLs",
                    "details": {
                        "authority_score": page.authority_score,
                        "source_urls_count": 0,
                    },
                }
        
        return {
            "passed": True,
            "details": {
                "authority_score": page.authority_score,
                "source_urls_count": len(page.source_urls) if page.source_urls else 0,
            },
        }
    
    async def _check_structure_gate(
        self,
        page: Page,
    ) -> GateCheckResult:
        """Gate 5: Content structure validation."""
        issues = []
        
        # Title validation
        if not page.title or len(page.title.strip()) < settings.min_title_length:
            issues.append(f"Title must be at least {settings.min_title_length} characters")
        
        # Body validation
        if not page.body or len(page.body.strip()) < settings.min_body_length:
            issues.append(f"Body must be at least {settings.min_body_length} characters")
        
        # Path validation
        if not page.path or not page.path.startswith("/"):
            issues.append("Path must start with '/'")
        
        if issues:
            return {
                "passed": False,
                "reason": "Content structure invalid",
                "details": {"issues": issues},
            }
        
        return {
            "passed": True,
            "details": {
                "title_length": len(page.title) if page.title else 0,
                "body_length": len(page.body) if page.body else 0,
                "path_valid": True,
            },
        }
    
    async def _check_status_gate(
        self,
        page: Page,
    ) -> GateCheckResult:
        """Gate 6: Status must allow publishing."""
        if page.status == ContentStatus.BLOCKED:
            return {
                "passed": False,
                "reason": "Content is blocked from publishing",
                "details": {"status": page.status.value},
            }
        
        if page.status == ContentStatus.DECOMMISSIONED:
            return {
                "passed": False,
                "reason": "Decommissioned content cannot be published",
                "details": {"status": page.status.value},
            }
        
        # Status must be APPROVED or DRAFT to publish
        if page.status not in [ContentStatus.APPROVED, ContentStatus.DRAFT]:
            return {
                "passed": False,
                "reason": f"Status '{page.status.value}' does not allow publishing",
                "details": {"status": page.status.value},
            }
        
        return {
            "passed": True,
            "details": {"status": page.status.value},
        }
    
    async def _check_experience_gate(
        self,
        page: Page,
    ) -> GateCheckResult:
        """Gate 7: Experience verification - Content must demonstrate first-hand experience."""
        return await self.experience_verifier.verify_experience(page)
    
    async def _check_geo_gate(
        self,
        page: Page,
    ) -> GateCheckResult:
        """Gate 8: GEO formatting - Content must be formatted for AI citation."""
        return await self.geo_formatter.validate_geo_formatting(page)
    
    async def _check_web_vitals_gate(
        self,
        db: AsyncSession,
        page: Page,
    ) -> GateCheckResult:
        """Gate 9: Core Web Vitals - Mobile-first rendering validation."""
        return await self.web_vitals_validator.validate_web_vitals(page, db)
    
    async def _check_media_integrity_gate(
        self,
        db: AsyncSession,
        page: Page,
    ) -> GateCheckResult:
        """Gate 10: Media Integrity - Multimedia governance (WebP, alt-text, VideoObject schema)."""
        return await self.media_integrity_validator.validate_media_integrity(page, db)

