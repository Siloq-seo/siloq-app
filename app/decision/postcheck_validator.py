"""Post-generation validation with full vector similarity checks."""
from typing import Dict, List, Optional, Tuple
from uuid import UUID
import re
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.decision.error_codes import ErrorCode, ErrorCodeDictionary
from app.decision.schemas import ValidationResult
from app.db.models import Page
from app.governance.near_duplicate_detector import NearDuplicateDetector, DetectionResult
from app.governance.geo_exceptions import GeoException
from app.governance.cannibalization import CannibalizationDetector
from app.core.config import settings


class PostCheckValidator:
    """
    Validates content after generation with full embedding-based checks.
    
    Performs comprehensive similarity checks using actual embeddings
    to detect near-duplicate intent and cannibalization.
    """
    
    def __init__(self):
        """Initialize post-check validator."""
        self.near_duplicate_detector = NearDuplicateDetector()
        self.cannibalization_detector = CannibalizationDetector()
    
    async def validate(
        self,
        db: AsyncSession,
        page_id: UUID,
        embedding: List[float],
        structured_output_metadata: Optional[Dict] = None,
    ) -> ValidationResult:
        """
        Run post-generation validation checks.
        
        Week 5: Enhanced with entity coverage, FAQ minimum, and link validation.
        
        Args:
            db: Database session
            page_id: Page identifier
            embedding: Generated content embedding
            structured_output_metadata: Optional metadata from structured output (entities, FAQs, links)
            
        Returns:
            ValidationResult with passed status and any errors/warnings
        """
        errors: List[Dict[str, str]] = []
        warnings: List[Dict[str, str]] = []
        
        # Get page for site_id
        page = await db.get(Page, page_id)
        if not page:
            errors.append(
                self._error_to_dict(ErrorCodeDictionary.SYSTEM_001)
            )
            return ValidationResult(
                passed=False,
                errors=errors,
                warnings=warnings,
                state="postcheck_failed",
            )
        
        # Week 5: Check structured output metadata if available
        if structured_output_metadata:
            # Check entity coverage
            entities = structured_output_metadata.get("entities", [])
            if len(entities) < settings.min_entity_count:
                errors.append(
                    self._error_to_dict(ErrorCodeDictionary.POSTCHECK_007)
                )
            
            # Check FAQ minimum
            faqs = structured_output_metadata.get("faqs", [])
            if len(faqs) < settings.min_faq_count:
                errors.append(
                    self._error_to_dict(ErrorCodeDictionary.POSTCHECK_008)
                )
            else:
                # Validate FAQ schema (each FAQ must have question and answer)
                for i, faq in enumerate(faqs):
                    if not isinstance(faq, dict):
                        errors.append(
                            self._error_to_dict(ErrorCodeDictionary.POSTCHECK_010)
                        )
                        break
                    if "question" not in faq or "answer" not in faq:
                        errors.append(
                            self._error_to_dict(ErrorCodeDictionary.POSTCHECK_010)
                        )
                        break
                    if not faq.get("question") or not faq.get("answer"):
                        errors.append(
                            self._error_to_dict(ErrorCodeDictionary.POSTCHECK_010)
                        )
                        break
            
            # Check link rules (no hallucinated links)
            links = structured_output_metadata.get("links", [])
            invalid_links = self._validate_links(links)
            if invalid_links:
                errors.append(
                    self._error_to_dict(ErrorCodeDictionary.POSTCHECK_009)
                )
        
        # Check 1: Near-duplicate intent detection
        detection_result = await self.near_duplicate_detector.detect_near_duplicates(
            db, page_id, embedding, page.site_id
        )
        
        # Check geo-exception if near-duplicate detected
        if detection_result.is_duplicate:
            # Check if geo-exception applies
            similar_content = detection_result.similar_content
            if similar_content:
                most_similar = similar_content[0]
                similar_page_id = UUID(most_similar.page_id)
                
                is_exception, reason = await GeoException.is_geo_exception(
                    db, page_id, similar_page_id
                )
                
                if is_exception:
                    # Geo-exception applies - allow it
                    warnings.append(
                        {
                            "code": "GEO_EXCEPTION",
                            "message": f"Near-duplicate detected but geo-exception applies: {reason}",
                            "severity": "warning",
                        }
                    )
                else:
                    # No geo-exception - block it
                    error_code = detection_result.error_code or ErrorCodeDictionary.NEAR_DUPLICATE_INTENT
                    errors.append(self._error_to_dict(error_code))
        elif detection_result.similarity_level.value == "similar_intent":
            # Similar but not blocking - add warning
            warnings.append(
                {
                    "code": "SIMILAR_INTENT",
                    "message": f"Similar intent detected (similarity: {detection_result.max_similarity:.2f})",
                    "severity": "warning",
                }
            )
        
        # Check 2: Full cannibalization check
        cannibalization_result = await self.cannibalization_detector.check_cannibalization(
            db,
            str(page_id),
            embedding,
            str(page.site_id),
        )
        
        if cannibalization_result["is_cannibalized"]:
            # Check geo-exception
            similar_content = cannibalization_result.get("similar_content", [])
            if similar_content:
                similar_page_id = UUID(similar_content[0]["id"])
                is_exception, reason = await GeoException.is_geo_exception(
                    db, page_id, similar_page_id
                )
                
                if not is_exception:
                    errors.append(
                        self._error_to_dict(ErrorCodeDictionary.PREFLIGHT_007)
                    )
                else:
                    warnings.append(
                        {
                            "code": "GEO_EXCEPTION",
                            "message": f"Cannibalization detected but geo-exception applies: {reason}",
                            "severity": "warning",
                        }
                    )
        
        # Log similarity scores
        await self._log_similarity_scores(
            db, page_id, detection_result, cannibalization_result
        )
        
        passed = len(errors) == 0
        
        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            state="postcheck_passed" if passed else "postcheck_failed",
        )
    
    def _validate_links(self, links: List[Dict[str, str]]) -> List[str]:
        """
        Week 5: Validate links - ensure no hallucinated links.
        
        Args:
            links: List of link dictionaries with 'url' and 'anchor_text' keys
            
        Returns:
            List of invalid link URLs (empty if all valid)
        """
        invalid_links = []
        
        for link in links:
            if not isinstance(link, dict):
                invalid_links.append("invalid_link_format")
                continue
            
            url = link.get("url", "")
            anchor_text = link.get("anchor_text", "")
            
            # Check URL format
            if not url:
                invalid_links.append("missing_url")
                continue
            
            # Validate URL format
            try:
                parsed = urlparse(url)
                # Must have scheme (http/https)
                if not parsed.scheme:
                    invalid_links.append(url)
                    continue
                
                # Must have netloc (domain)
                if not parsed.netloc:
                    invalid_links.append(url)
                    continue
                
                # Check for common hallucination patterns
                # These are patterns that suggest the URL was made up
                hallucination_patterns = [
                    r'example\.com',
                    r'placeholder',
                    r'\.\.\.',
                    r'\[url\]',
                    r'\[link\]',
                    r'http://localhost',
                    r'http://test',
                ]
                
                url_lower = url.lower()
                for pattern in hallucination_patterns:
                    if re.search(pattern, url_lower):
                        invalid_links.append(url)
                        break
                
            except Exception:
                invalid_links.append(url)
        
        return invalid_links
    
    async def _log_similarity_scores(
        self,
        db: AsyncSession,
        page_id: UUID,
        detection_result: DetectionResult,
        cannibalization_result: dict,
    ) -> None:
        """
        Log similarity scores to cannibalization_checks table.
        
        Args:
            db: Database session
            page_id: Page identifier
            detection_result: Near-duplicate detection result
            cannibalization_result: Cannibalization check result
        """
        from app.db.models import CannibalizationCheck
        
        # Log near-duplicate detections
        for similar_content in detection_result.similar_content:
            check = CannibalizationCheck(
                page_id=page_id,
                compared_with_id=UUID(similar_content.page_id),
                similarity_score=similar_content.similarity,
                threshold_exceeded=similar_content.similarity >= 0.85,
            )
            db.add(check)
        
        # Log cannibalization checks (if not already logged)
        similar_content = cannibalization_result.get("similar_content", [])
        for item in similar_content:
            # Check if already logged
            existing_query = (
                select(CannibalizationCheck)
                .where(
                    CannibalizationCheck.page_id == page_id,
                    CannibalizationCheck.compared_with_id == UUID(item["id"]),
                )
            )
            result = await db.execute(existing_query)
            if not result.scalar_one_or_none():
                check = CannibalizationCheck(
                    page_id=page_id,
                    compared_with_id=UUID(item["id"]),
                    similarity_score=item["similarity"],
                    threshold_exceeded=item["similarity"] >= 0.85,
                )
                db.add(check)
        
        await db.commit()
    
    @staticmethod
    def _error_to_dict(error: ErrorCode) -> Dict[str, str]:
        """Convert ErrorCode to dictionary for API response."""
        return error.to_dict()

