"""
2026 Governance Enhancement: GBP Signal Validator (Google Business Profile Integration)

In 2025, Local SEO is no longer just about "being there"—it's about "Local Social Proof."
Siloq needs to bridge the gap between the website and the Google Business Profile (GBP).

This module validates that entities mentioned on local service pages match the
"Attributes" and "Services" listed on the business's GBP. If there is a mismatch,
it flags it as an "Authority Leak."
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Page, SystemEvent
from app.core.config import settings


class GBPValidator:
    """
    Validates Google Business Profile (GBP) signal alignment.
    
    Ensures that:
    - Services mentioned on local pages match GBP services
    - Attributes mentioned match GBP attributes
    - No authority leakage from mismatches
    """
    
    def __init__(self):
        # In a full implementation, this would integrate with Google Business Profile API
        # For now, we'll use a mock/stub approach
        self.gbp_api_enabled = False  # Would be set via config
    
    async def validate_gbp_alignment(
        self,
        db: AsyncSession,
        page: Page,
        gbp_place_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate that page content aligns with Google Business Profile.
        
        Args:
            db: Database session
            page: Page to validate (should be a local service page)
            gbp_place_id: Optional GBP Place ID (if not provided, will try to find from page metadata)
            
        Returns:
            Validation result with alignment status
        """
        issues = []
        warnings = []
        details = {}
        
        # Get GBP Place ID if not provided
        if not gbp_place_id:
            gbp_place_id = await self._get_gbp_place_id_from_page(db, page)
        
        if not gbp_place_id:
            # If no GBP Place ID, return warning (not blocking)
            return {
                "valid": True,
                "warnings": ["No GBP Place ID found. GBP alignment validation skipped."],
                "details": {"gbp_place_id": None},
            }
        
        # Get GBP data (services, attributes, etc.)
        gbp_data = await self._fetch_gbp_data(gbp_place_id)
        
        if not gbp_data:
            warnings.append(f"Could not fetch GBP data for Place ID: {gbp_place_id}")
            return {
                "valid": True,
                "warnings": warnings,
                "details": {"gbp_place_id": gbp_place_id},
            }
        
        # Extract services/attributes from page content
        page_entities = await self._extract_page_entities(page)
        
        # Validate service alignment
        service_alignment = await self._validate_service_alignment(
            page_entities.get("services", []),
            gbp_data.get("services", []),
        )
        
        if not service_alignment["aligned"]:
            issues.extend(service_alignment["mismatches"])
            details["service_mismatches"] = service_alignment["mismatches"]
        
        details["page_services_count"] = len(page_entities.get("services", []))
        details["gbp_services_count"] = len(gbp_data.get("services", []))
        details["service_alignment_score"] = service_alignment.get("alignment_score", 0.0)
        
        # Validate attribute alignment
        attribute_alignment = await self._validate_attribute_alignment(
            page_entities.get("attributes", []),
            gbp_data.get("attributes", []),
        )
        
        if not attribute_alignment["aligned"]:
            issues.extend(attribute_alignment["mismatches"])
            details["attribute_mismatches"] = attribute_alignment["mismatches"]
        
        details["page_attributes_count"] = len(page_entities.get("attributes", []))
        details["gbp_attributes_count"] = len(gbp_data.get("attributes", []))
        details["attribute_alignment_score"] = attribute_alignment.get("alignment_score", 0.0)
        
        # Determine if authority leak exists
        authority_leak = len(issues) > 0
        
        if authority_leak:
            # Log authority leak
            audit = SystemEvent(
                event_type="gbp_authority_leak_detected",
                entity_type="page",
                entity_id=page.id,
                payload={
                    "gbp_place_id": gbp_place_id,
                    "service_mismatches": service_alignment.get("mismatches", []),
                    "attribute_mismatches": attribute_alignment.get("mismatches", []),
                },
            )
            db.add(audit)
        
        return {
            "valid": not authority_leak,
            "aligned": not authority_leak,
            "authority_leak": authority_leak,
            "issues": issues,
            "warnings": warnings,
            "details": details,
            "gbp_place_id": gbp_place_id,
        }
    
    async def _get_gbp_place_id_from_page(
        self,
        db: AsyncSession,
        page: Page,
    ) -> Optional[str]:
        """Get GBP Place ID from page metadata."""
        # In a real implementation, GBP Place ID would be stored in:
        # - Page metadata
        # - Site metadata
        # - Governance checks
        
        if page.governance_checks:
            return page.governance_checks.get("gbp_place_id")
        
        # Could also check site metadata
        return None
    
    async def _fetch_gbp_data(
        self,
        gbp_place_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch Google Business Profile data.
        
        In a full implementation, this would use the Google Business Profile API
        (formerly Google My Business API) to fetch:
        - Services/primary categories
        - Attributes
        - Business hours
        - Reviews/sentiment
        
        For now, returns mock data structure.
        """
        # TODO: Integrate with Google Business Profile API
        # Example API call would be:
        # response = await gbp_api_client.get_place(gbp_place_id)
        # return {
        #     "services": response.get("primary_category", []) + response.get("additional_categories", []),
        #     "attributes": response.get("attributes", []),
        #     ...
        # }
        
        # Mock data structure
        return {
            "services": [],
            "attributes": [],
            "place_id": gbp_place_id,
        }
    
    async def _extract_page_entities(
        self,
        page: Page,
    ) -> Dict[str, List[str]]:
        """
        Extract services and attributes from page content.
        
        In a full implementation, this would use entity extraction/NER
        to identify services and attributes mentioned in the content.
        """
        entities = {
            "services": [],
            "attributes": [],
        }
        
        if not page.body:
            return entities
        
        # Check governance_checks for structured entities
        if page.governance_checks:
            structured_entities = page.governance_checks.get("entities", [])
            for entity in structured_entities:
                entity_type = entity.get("type", "")
                entity_name = entity.get("name", "")
                
                if entity_type in ["service", "Service"]:
                    entities["services"].append(entity_name)
                elif entity_type in ["attribute", "Attribute", "feature"]:
                    entities["attributes"].append(entity_name)
        
        # Could also extract from body text using NLP/entity extraction
        # For now, rely on structured entities in governance_checks
        
        return entities
    
    async def _validate_service_alignment(
        self,
        page_services: List[str],
        gbp_services: List[str],
    ) -> Dict[str, Any]:
        """
        Validate that page services align with GBP services.
        
        Args:
            page_services: Services mentioned on the page
            gbp_services: Services listed in GBP
            
        Returns:
            Alignment validation result
        """
        mismatches = []
        
        if not gbp_services:
            # If no GBP services, can't validate
            return {
                "aligned": True,
                "mismatches": [],
                "alignment_score": 1.0,
            }
        
        if not page_services:
            return {
                "aligned": True,
                "mismatches": [],
                "alignment_score": 1.0,
            }
        
        # Normalize service names for comparison
        gbp_services_normalized = [s.lower().strip() for s in gbp_services]
        page_services_normalized = [s.lower().strip() for s in page_services]
        
        # Find services mentioned on page that are NOT in GBP
        unmatched_services = [
            page_service
            for page_service in page_services
            if page_service.lower().strip() not in gbp_services_normalized
        ]
        
        if unmatched_services:
            mismatches.append(
                f"Services mentioned on page but not in GBP: {', '.join(unmatched_services)}. "
                "This creates an authority leak."
            )
        
        # Calculate alignment score (percentage of page services that match GBP)
        matched_count = len(page_services) - len(unmatched_services)
        alignment_score = matched_count / len(page_services) if page_services else 1.0
        
        return {
            "aligned": len(mismatches) == 0,
            "mismatches": mismatches,
            "alignment_score": alignment_score,
            "unmatched_services": unmatched_services,
        }
    
    async def _validate_attribute_alignment(
        self,
        page_attributes: List[str],
        gbp_attributes: List[str],
    ) -> Dict[str, Any]:
        """
        Validate that page attributes align with GBP attributes.
        
        Args:
            page_attributes: Attributes mentioned on the page
            gbp_attributes: Attributes listed in GBP
            
        Returns:
            Alignment validation result
        """
        mismatches = []
        
        if not gbp_attributes:
            # If no GBP attributes, can't validate
            return {
                "aligned": True,
                "mismatches": [],
                "alignment_score": 1.0,
            }
        
        if not page_attributes:
            return {
                "aligned": True,
                "mismatches": [],
                "alignment_score": 1.0,
            }
        
        # Normalize attribute names for comparison
        gbp_attributes_normalized = [a.lower().strip() for a in gbp_attributes]
        page_attributes_normalized = [a.lower().strip() for a in page_attributes]
        
        # Find attributes mentioned on page that are NOT in GBP
        unmatched_attributes = [
            page_attribute
            for page_attribute in page_attributes
            if page_attribute.lower().strip() not in gbp_attributes_normalized
        ]
        
        if unmatched_attributes:
            mismatches.append(
                f"Attributes mentioned on page but not in GBP: {', '.join(unmatched_attributes)}. "
                "This creates an authority leak."
            )
        
        # Calculate alignment score
        matched_count = len(page_attributes) - len(unmatched_attributes)
        alignment_score = matched_count / len(page_attributes) if page_attributes else 1.0
        
        return {
            "aligned": len(mismatches) == 0,
            "mismatches": mismatches,
            "alignment_score": alignment_score,
            "unmatched_attributes": unmatched_attributes,
        }
    
    async def suggest_gbp_updates(
        self,
        page_services: List[str],
        page_attributes: List[str],
        gbp_services: List[str],
        gbp_attributes: List[str],
    ) -> Dict[str, List[str]]:
        """
        Suggest GBP updates based on page content.
        
        Returns services/attributes that should be added to GBP to match page content.
        """
        suggestions = {
            "services_to_add": [],
            "attributes_to_add": [],
        }
        
        # Find services/attributes on page that aren't in GBP
        gbp_services_normalized = [s.lower().strip() for s in gbp_services]
        gbp_attributes_normalized = [a.lower().strip() for a in gbp_attributes]
        
        for service in page_services:
            if service.lower().strip() not in gbp_services_normalized:
                suggestions["services_to_add"].append(service)
        
        for attribute in page_attributes:
            if attribute.lower().strip() not in gbp_attributes_normalized:
                suggestions["attributes_to_add"].append(attribute)
        
        return suggestions

