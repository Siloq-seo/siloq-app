"""Anchor text governance for authority management."""
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.models import Page, AnchorLink, PageSilo
from app.governance.authority_funnel import AuthorityFunnel

# Constants
DEFAULT_AUTHORITY_PASS = 0.1  # 10% authority passed per link
MAX_AUTHORITY_PASS = 0.2  # Maximum 20% authority per link
MIN_ANCHOR_TEXT_LENGTH = 2
MAX_ANCHOR_TEXT_LENGTH = 100
AUTHORITY_MULTIPLIER = 0.1  # 10% of source authority


class AnchorGovernor:
    """
    Governs anchor text and internal linking.
    
    Ensures:
    - Anchor text is appropriate and relevant
    - Authority flows correctly (no sideways leakage)
    - Anchor links are tracked with authority metrics
    """
    
    async def create_anchor_link(
        self,
        db: AsyncSession,
        from_page_id: UUID,
        to_page_id: UUID,
        anchor_text: str,
        authority_passed: Optional[float] = None,
    ) -> Tuple[bool, str, Optional[AnchorLink]]:
        """
        Create a governed anchor link between two pages.
        
        Validates pages exist, anchor text is appropriate, and authority
        flow is allowed before creating the link.
        
        Args:
            db: Database session
            from_page_id: Source page identifier
            to_page_id: Target page identifier
            anchor_text: Anchor text for the link
            authority_passed: Authority amount passed (auto-calculated if None)
            
        Returns:
            Tuple of (success, message, anchor_link_or_none)
        """
        # Validate pages exist
        validation_result = await self._validate_pages(db, from_page_id, to_page_id)
        if not validation_result[0]:
            return (*validation_result, None)
        
        from_page, to_page = validation_result[1]
        
        # Validate anchor text
        text_valid, text_message = self.validate_anchor_text(anchor_text, to_page)
        if not text_valid:
            return (False, text_message, None)
        
        # Validate authority flow
        is_valid, reason = await AuthorityFunnel.validate_authority_flow(
            db, from_page_id, to_page_id
        )
        if not is_valid:
            return (False, reason, None)
        
        # Get shared silo if pages are in same silo
        silo_id = await self._get_shared_silo_id(db, from_page_id, to_page_id)
        
        # Calculate authority passed
        if authority_passed is None:
            authority_passed = self._calculate_authority_passed(from_page)
        
        # Create anchor link
        return await self._create_link(
            db, from_page_id, to_page_id, anchor_text, silo_id, authority_passed
        )
    
    async def _validate_pages(
        self,
        db: AsyncSession,
        from_page_id: UUID,
        to_page_id: UUID,
    ) -> Tuple[bool, Optional[Tuple[Page, Page]], str]:
        """Validate that both pages exist."""
        from_page = await db.get(Page, from_page_id)
        to_page = await db.get(Page, to_page_id)
        
        if not from_page or not to_page:
            return (False, None, "One or both pages not found")
        
        return (True, (from_page, to_page), "")
    
    def validate_anchor_text(
        self,
        anchor_text: str,
        target_page: Page,
    ) -> Tuple[bool, str]:
        """
        Validate anchor text quality and relevance.
        
        Checks length, relevance to target page title/keyword.
        
        Args:
            anchor_text: Anchor text to validate
            target_page: Target page for the link
            
        Returns:
            Tuple of (is_valid, reason_message)
        """
        # Length validation
        if not anchor_text or len(anchor_text.strip()) < MIN_ANCHOR_TEXT_LENGTH:
            return (False, f"Anchor text too short (minimum {MIN_ANCHOR_TEXT_LENGTH} characters)")
        
        if len(anchor_text) > MAX_ANCHOR_TEXT_LENGTH:
            return (False, f"Anchor text too long (maximum {MAX_ANCHOR_TEXT_LENGTH} characters)")
        
        # Relevance validation
        return self._check_relevance(anchor_text, target_page)
    
    def _check_relevance(
        self,
        anchor_text: str,
        target_page: Page,
    ) -> Tuple[bool, str]:
        """Check if anchor text is relevant to target page."""
        anchor_lower = anchor_text.lower()
        title_lower = (target_page.title or "").lower()
        
        # Check if anchor text appears in title or vice versa
        if anchor_lower in title_lower or title_lower in anchor_lower:
            return (True, "Anchor text is relevant to target page title")
        
        # Check keyword relevance
        if target_page.keyword:
            keyword_lower = target_page.keyword.keyword.lower()
            if keyword_lower in anchor_lower:
                return (True, "Anchor text contains target keyword")
        
        # Allow but warn
        return (True, "Anchor text may not be optimally relevant")
    
    def _calculate_authority_passed(self, from_page: Page) -> float:
        """Calculate authority to pass based on source page authority."""
        base_authority = DEFAULT_AUTHORITY_PASS
        
        if from_page.authority_score:
            calculated = from_page.authority_score * AUTHORITY_MULTIPLIER
            base_authority = min(MAX_AUTHORITY_PASS, calculated)
        
        return base_authority
    
    async def _get_shared_silo_id(
        self,
        db: AsyncSession,
        from_page_id: UUID,
        to_page_id: UUID,
    ) -> Optional[UUID]:
        """Get shared silo ID if both pages are in the same silo."""
        from_silo_ids = await AuthorityFunnel._get_page_silo_ids(db, from_page_id)
        to_silo_ids = await AuthorityFunnel._get_page_silo_ids(db, to_page_id)
        
        shared_silos = from_silo_ids.intersection(to_silo_ids)
        return list(shared_silos)[0] if shared_silos else None
    
    async def _create_link(
        self,
        db: AsyncSession,
        from_page_id: UUID,
        to_page_id: UUID,
        anchor_text: str,
        silo_id: Optional[UUID],
        authority_passed: float,
    ) -> Tuple[bool, str, Optional[AnchorLink]]:
        """Create the anchor link in the database."""
        anchor_link = AnchorLink(
            from_page_id=from_page_id,
            to_page_id=to_page_id,
            anchor_text=anchor_text,
            silo_id=silo_id,
            is_internal=True,
            authority_passed=authority_passed,
        )
        
        try:
            db.add(anchor_link)
            await db.commit()
            await db.refresh(anchor_link)
            return (True, "Anchor link created", anchor_link)
        except Exception as e:
            await db.rollback()
            return (False, f"Failed to create anchor link: {str(e)}", None)
    
    async def get_anchor_links_for_page(
        self,
        db: AsyncSession,
        page_id: UUID,
        direction: str = "outbound",
    ) -> List[Dict]:
        """
        Get anchor links for a page.
        
        Args:
            db: Database session
            page_id: Page identifier
            direction: Link direction - 'outbound', 'inbound', or 'both'
            
        Returns:
            List of anchor link dictionaries with metadata
        """
        links: List[Dict] = []
        
        if direction in ("outbound", "both"):
            links.extend(await self._get_outbound_links(db, page_id))
        
        if direction in ("inbound", "both"):
            links.extend(await self._get_inbound_links(db, page_id))
        
        return links
    
    async def _get_outbound_links(
        self,
        db: AsyncSession,
        page_id: UUID,
    ) -> List[Dict]:
        """Get outbound anchor links from a page."""
        query = (
            select(AnchorLink, Page)
            .join(Page, AnchorLink.to_page_id == Page.id)
            .where(AnchorLink.from_page_id == page_id)
        )
        
        result = await db.execute(query)
        return [
            {
                "id": str(anchor_link.id),
                "direction": "outbound",
                "to_page_id": str(to_page.id),
                "to_page_title": to_page.title,
                "anchor_text": anchor_link.anchor_text,
                "authority_passed": anchor_link.authority_passed,
                "silo_id": str(anchor_link.silo_id) if anchor_link.silo_id else None,
            }
            for anchor_link, to_page in result
        ]
    
    async def _get_inbound_links(
        self,
        db: AsyncSession,
        page_id: UUID,
    ) -> List[Dict]:
        """Get inbound anchor links to a page."""
        query = (
            select(AnchorLink, Page)
            .join(Page, AnchorLink.from_page_id == Page.id)
            .where(AnchorLink.to_page_id == page_id)
        )
        
        result = await db.execute(query)
        return [
            {
                "id": str(anchor_link.id),
                "direction": "inbound",
                "from_page_id": str(from_page.id),
                "from_page_title": from_page.title,
                "anchor_text": anchor_link.anchor_text,
                "authority_passed": anchor_link.authority_passed,
                "silo_id": str(anchor_link.silo_id) if anchor_link.silo_id else None,
            }
            for anchor_link, from_page in result
        ]
