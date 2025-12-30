"""Local SEO geo-exception logic for geographic content differentiation."""
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Page


class GeoException:
    """
    Handles geographic exceptions for local SEO content.
    
    Allows same intent content when locations differ, but blocks
    when intent and location are the same.
    """
    
    @staticmethod
    def extract_location_from_title(title: str) -> Optional[str]:
        """
        Extract location from title (simple implementation).
        
        This is a basic implementation. In production, you might:
        - Use NLP to extract location entities
        - Parse structured location data
        - Use geocoding services
        
        Args:
            title: Page title
            
        Returns:
            Extracted location string or None
        """
        # Common location patterns
        location_indicators = [
            " in ",
            " near ",
            " at ",
            ", ",
        ]
        
        title_lower = title.lower()
        
        # Try to find location after common indicators
        for indicator in location_indicators:
            if indicator in title_lower:
                parts = title_lower.split(indicator, 1)
                if len(parts) > 1:
                    # Take the part after the indicator
                    location = parts[1].strip()
                    # Remove common trailing words
                    for word in ["guide", "tips", "review", "best", "top"]:
                        if location.endswith(f" {word}"):
                            location = location[:-len(f" {word}")].strip()
                    return location.title() if location else None
        
        return None
    
    @staticmethod
    async def get_page_location(
        db: AsyncSession, page_id: UUID
    ) -> Optional[str]:
        """
        Get location metadata for a page.
        
        Checks:
        1. Explicit location metadata field (if exists)
        2. Extracted from title
        3. Extracted from path
        
        Args:
            db: Database session
            page_id: Page identifier
            
        Returns:
            Location string or None
        """
        page = await db.get(Page, page_id)
        if not page:
            return None
        
        # TODO: Check for explicit location metadata field
        # For now, extract from title
        if page.title:
            location = GeoException.extract_location_from_title(page.title)
            if location:
                return location
        
        # Try extracting from path
        if page.path:
            # Path might contain location (e.g., /nyc/best-pizza)
            path_parts = page.path.strip("/").split("/")
            if len(path_parts) > 1:
                # First part might be location
                potential_location = path_parts[0]
                # Validate it looks like a location (simple check)
                if len(potential_location) > 2 and potential_location.isalpha():
                    return potential_location.upper()
        
        return None
    
    @staticmethod
    async def is_geo_exception(
        db: AsyncSession, page1_id: UUID, page2_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if two pages qualify for geo-exception.
        
        Geo-exception applies when:
        - Same intent (high similarity)
        - Different locations
        - Both have valid location metadata
        
        Args:
            db: Database session
            page1_id: First page identifier
            page2_id: Second page identifier
            
        Returns:
            Tuple of (is_exception, reason)
        """
        location1 = await GeoException.get_page_location(db, page1_id)
        location2 = await GeoException.get_page_location(db, page2_id)
        
        # Both pages must have locations for geo-exception
        if not location1 or not location2:
            return False, "One or both pages missing location metadata"
        
        # Locations must be different
        if location1.lower() == location2.lower():
            return False, "Same location, no geo-exception"
        
        # Different locations = geo-exception applies
        return True, f"Different locations: {location1} vs {location2}"
    
    @staticmethod
    def normalize_location(location: str) -> str:
        """
        Normalize location string for comparison.
        
        Args:
            location: Location string
            
        Returns:
            Normalized location string
        """
        # Convert to lowercase, remove common variations
        normalized = location.lower().strip()
        
        # Handle common abbreviations
        abbreviations = {
            "nyc": "new york",
            "ny": "new york",
            "la": "los angeles",
            "sf": "san francisco",
            "chi": "chicago",
        }
        
        for abbrev, full in abbreviations.items():
            if normalized == abbrev:
                normalized = full
        
        return normalized

