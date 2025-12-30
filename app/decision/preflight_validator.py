"""Preflight Validator - Check all conditions before allowing generation."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.decision.error_codes import ErrorCode, ErrorCodeDictionary
from app.decision.schemas import ValidationPayload, ValidationResult
from app.db.models import Page, Site, Silo, Keyword
from app.governance.reverse_silos import ReverseSiloEnforcer
from app.governance.cannibalization import CannibalizationDetector
from app.governance.near_duplicate_detector import NearDuplicateDetector
from app.governance.geo_exceptions import GeoException
from app.governance.reservation_system import ReservationSystem


# Constants
PROPOSAL_DECAY_THRESHOLD_DAYS = 90
MIN_TITLE_LENGTH = 10


class PreflightValidator:
    """
    Validates all conditions before allowing content generation.
    
    Runs comprehensive preflight checks including:
    - Site existence and structure
    - Path uniqueness and format
    - Title validation
    - Silo structure and ownership
    - Keyword uniqueness
    - Proposal decay checks
    - Initial cannibalization checks
    """
    
    def __init__(self):
        """Initialize preflight validator with governance components."""
        self.silo_enforcer = ReverseSiloEnforcer()
        self.cannibalization_detector = CannibalizationDetector()
        self.near_duplicate_detector = NearDuplicateDetector()
        self.reservation_system = ReservationSystem()
    
    async def validate(
        self, db: AsyncSession, payload: ValidationPayload
    ) -> ValidationResult:
        """
        Run all preflight validation checks.
        
        Args:
            db: Database session
            payload: Validation payload with page data
            
        Returns:
            ValidationResult with passed status and any errors/warnings
        """
        errors: List[Dict[str, str]] = []
        warnings: List[Dict[str, str]] = []
        
        # Run all validation checks
        validation_checks = [
            self._check_site_exists(db, payload.site_id),
            self._check_path_uniqueness(
                db, payload.site_id, payload.path, payload.page_id
            ),
            self._check_path_format(payload.path),
            self._check_title_length(payload.title),
        ]
        
        # Conditional checks
        if payload.silo_id:
            validation_checks.append(
                self._check_silo_structure(db, payload.site_id, payload.silo_id)
            )
        
        if payload.keyword:
            validation_checks.append(
                self._check_keyword_uniqueness(db, payload.keyword, payload.page_id)
            )
        
        if payload.is_proposal:
            validation_checks.append(
                self._check_proposal_decay(db, payload.page_id)
            )
        
        # Execute all checks
        for check_result in validation_checks:
            passed, error_or_warning = await check_result
            if not passed and error_or_warning:
                if error_or_warning.severity == "warning":
                    warnings.append(error_or_warning.to_dict())
                else:
                    errors.append(error_or_warning.to_dict())
        
        # Initial cannibalization check (warning only)
        cannibalization_warning = await self._check_initial_cannibalization(
            db, payload.site_id, payload.title, payload.page_id
        )
        if cannibalization_warning:
            warnings.append(cannibalization_warning.to_dict())
        
        passed = len(errors) == 0
        
        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            state="preflight_approved" if passed else "draft",
        )
    
    async def _check_site_exists(
        self, db: AsyncSession, site_id: UUID
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check if site exists.
        
        Args:
            db: Database session
            site_id: Site identifier
            
        Returns:
            Tuple of (exists, error_code_if_not)
        """
        site = await db.get(Site, site_id)
        if not site:
            return False, ErrorCodeDictionary.PREFLIGHT_009
        return True, None
    
    async def _check_path_uniqueness(
        self, db: AsyncSession, site_id: UUID, path: str, page_id: UUID
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check if normalized path is unique within site.
        
        Args:
            db: Database session
            site_id: Site identifier
            path: Page path to check
            page_id: Current page ID (to exclude from check)
            
        Returns:
            Tuple of (is_unique, error_code_if_not)
        """
        normalized_path = path.lower().strip()
        
        query = select(Page).where(
            and_(
                Page.site_id == site_id,
                Page.normalized_path == normalized_path,
                Page.id != page_id,
            )
        )
        result = await db.execute(query)
        existing_page = result.scalar_one_or_none()
        
        if existing_page:
            return False, ErrorCodeDictionary.PREFLIGHT_001
        
        return True, None
    
    def _check_path_format(self, path: str) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check path format validity.
        
        Args:
            path: Path to validate
            
        Returns:
            Tuple of (is_valid, error_code_if_not)
        """
        if not path.startswith("/"):
            return False, ErrorCodeDictionary.PREFLIGHT_005
        return True, None
    
    def _check_title_length(self, title: str) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check title length validity.
        
        Args:
            title: Title to validate
            
        Returns:
            Tuple of (is_valid, error_code_if_not)
        """
        if len(title.strip()) < MIN_TITLE_LENGTH:
            return False, ErrorCodeDictionary.PREFLIGHT_004
        return True, None
    
    async def _check_silo_structure(
        self, db: AsyncSession, site_id: UUID, silo_id: UUID
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check silo structure and ownership.
        
        Args:
            db: Database session
            site_id: Site identifier
            silo_id: Silo identifier
            
        Returns:
            Tuple of (is_valid, error_code_if_not)
        """
        # Check silo exists and belongs to site
        silo = await db.get(Silo, silo_id)
        if not silo or silo.site_id != site_id:
            return False, ErrorCodeDictionary.PREFLIGHT_003
        
        # Check site has valid silo structure (3-7 silos)
        is_valid, _ = await self.silo_enforcer.validate_silo_structure(
            db, str(site_id)
        )
        if not is_valid:
            return False, ErrorCodeDictionary.PREFLIGHT_002
        
        return True, None
    
    async def _check_keyword_uniqueness(
        self, db: AsyncSession, keyword: str, page_id: UUID
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check keyword is not already mapped to another page.
        
        Args:
            db: Database session
            keyword: Keyword to check
            page_id: Current page ID (to exclude from check)
            
        Returns:
            Tuple of (is_unique, error_code_if_not)
        """
        normalized_keyword = keyword.lower().strip()
        
        query = select(Keyword).where(Keyword.keyword == normalized_keyword)
        result = await db.execute(query)
        existing_keyword = result.scalar_one_or_none()
        
        if existing_keyword and existing_keyword.page_id != page_id:
            return False, ErrorCodeDictionary.PREFLIGHT_006
        
        return True, None
    
    async def _check_proposal_decay(
        self, db: AsyncSession, page_id: UUID
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check if proposal has exceeded decay threshold.
        
        This is a warning, not an error. The SILO_DECAY trigger
        will handle actual decay.
        
        Args:
            db: Database session
            page_id: Page identifier
            
        Returns:
            Tuple of (is_valid, warning_if_exceeded)
        """
        page = await db.get(Page, page_id)
        if not page:
            return True, None
        
        if page.is_proposal and page.created_at:
            age = datetime.utcnow() - page.created_at
            if age > timedelta(days=PROPOSAL_DECAY_THRESHOLD_DAYS):
                return False, ErrorCodeDictionary.PREFLIGHT_008
        
        return True, None
    
    async def _check_initial_cannibalization(
        self,
        db: AsyncSession,
        site_id: UUID,
        title: str,
        page_id: UUID,
    ) -> Optional[ErrorCode]:
        """
        Initial cannibalization check using title (lightweight).
        
        This is a warning - full check happens post-generation with embeddings.
        
        Args:
            db: Database session
            site_id: Site identifier
            title: Page title
            page_id: Page identifier
            
        Returns:
            Warning ErrorCode if potential cannibalization detected, None otherwise
        """
        # TODO: Implement lightweight title-based similarity check
        # For now, return None (no warning)
        return None
