"""Helper utilities for Page model operations"""
from typing import Optional
from uuid import UUID
from app.db.models import Page


def get_page_silo_id(page: Page) -> Optional[UUID]:
    """
    Get the primary silo ID for a page.
    
    Pages have a many-to-many relationship with silos via page_silos.
    This helper returns the first silo ID if available.
    
    Args:
        page: Page instance
        
    Returns:
        Silo ID if page has silos, None otherwise
    """
    if page.page_silos:
        return page.page_silos[0].silo_id
    return None


def get_page_slug(page: Page) -> str:
    """
    Derive slug from page path.
    
    Args:
        page: Page instance
        
    Returns:
        Slug derived from path
    """
    if page.path == "/":
        return ""
    # Remove leading/trailing slashes and get last segment
    path_parts = page.path.strip("/").split("/")
    return path_parts[-1] if path_parts else ""


def is_safe_to_publish(page: Page) -> bool:
    """
    Calculate if page is safe to publish based on status and governance checks.
    
    Args:
        page: Page instance
        
    Returns:
        True if page is safe to publish, False otherwise
    """
    # Check status
    from app.db.models import ContentStatus
    if page.status in [ContentStatus.BLOCKED, ContentStatus.DECOMMISSIONED]:
        return False
    
    # Check governance checks if available
    if page.governance_checks:
        pre_gen = page.governance_checks.get("pre_generation", {}).get("passed", False)
        during_gen = page.governance_checks.get("during_generation", {}).get("passed", False)
        post_gen = page.governance_checks.get("post_generation", {}).get("passed", False)
        
        if not (pre_gen and during_gen and post_gen):
            return False
    
    # Must have embedding
    if not page.embedding:
        return False
    
    # Must have body
    if not page.body or len(page.body.strip()) < 500:
        return False
    
    return True

