"""Tenant isolation enforcement - Section 7"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status

from app.db.models import Project, Site, Page
from app.core.security.encryption import SecurityError


class TenantIsolationError(SecurityError):
    """Tenant isolation violation error"""
    pass


async def get_project_for_site(site_id: UUID, db: AsyncSession) -> Optional[Project]:
    """
    Get project for a site (1:1 relationship).
    
    Args:
        site_id: Site UUID
        db: Database session
        
    Returns:
        Project or None if not found
    """
    stmt = select(Project).where(
        and_(
            Project.site_id == site_id,
            Project.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def verify_project_access(
    project_id: UUID,
    user_organization_id: UUID,
    db: AsyncSession
) -> Project:
    """
    Verify that a user's organization has access to a project.
    
    Args:
        project_id: Project UUID
        user_organization_id: User's organization UUID
        db: Database session
        
    Returns:
        Project if access granted
        
    Raises:
        HTTPException: If access denied
    """
    project = await db.get(Project, project_id)
    
    if not project or project.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.organization_id != user_organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "CROSS_PROJECT_ACCESS_DENIED",
                "message": "Access denied: Project belongs to different organization",
                "remediation": "Ensure project belongs to your organization"
            }
        )
    
    return project


async def enforce_project_isolation(
    project_id: UUID,
    user_organization_id: UUID,
    db: AsyncSession
) -> Project:
    """
    Enforce project-level isolation (hard requirement).
    
    All queries MUST filter by project_id. This function ensures
    the project belongs to the user's organization.
    
    Args:
        project_id: Project UUID to verify
        user_organization_id: User's organization UUID
        db: Database session
        
    Returns:
        Project if isolation verified
        
    Raises:
        TenantIsolationError: If isolation violation detected
    """
    try:
        project = await verify_project_access(project_id, user_organization_id, db)
        return project
    except HTTPException as e:
        if e.status_code == status.HTTP_403_FORBIDDEN:
            raise TenantIsolationError(
                "CRITICAL: Cross-project access attempt detected. "
                "This is a security violation."
            )
        raise


def validate_query_scoping(query_str: str) -> bool:
    """
    Validate that a SQL query includes project_id filter.
    
    This is a basic validation - should be used as a safeguard,
    but proper enforcement should be at the ORM/application level.
    
    Args:
        query_str: SQL query string
        
    Returns:
        True if query appears to include project_id filter
    """
    query_lower = query_str.lower()
    
    # Check for project_id filter
    if "project_id" not in query_lower:
        return False
    
    # Check for WHERE clause with project_id
    if "where" in query_lower and "project_id" in query_lower:
        # Check if project_id is in WHERE clause
        where_index = query_lower.find("where")
        project_id_index = query_lower.find("project_id", where_index)
        
        if project_id_index > where_index:
            return True
    
    return False


async def detect_cross_project_leak(
    project_id: UUID,
    mentioned_entities: List[str],
    db: AsyncSession
) -> bool:
    """
    Detect if any mentioned entities belong to other projects.
    
    Used for prompt isolation validation to prevent cross-project
    context leakage in AI prompts.
    
    Args:
        project_id: Current project UUID
        mentioned_entities: List of entity names/IDs mentioned in prompt
        db: Database session
        
    Returns:
        True if cross-project leak detected, False otherwise
    """
    # Get all pages/entities for the current project
    # This is a placeholder - implement based on actual entity model
    # For now, just verify project exists
    project = await db.get(Project, project_id)
    
    if not project:
        return True  # Project not found = leak potential
    
    # TODO: Implement entity cross-check
    # For now, return False (no leak detected)
    return False


def build_project_scoped_query(base_query, project_id: UUID, alias=None):
    """
    Build a project-scoped query by adding project_id filter.
    
    This is a helper for ensuring all queries are project-scoped.
    
    Args:
        base_query: Base SQLAlchemy query
        project_id: Project UUID to filter by
        alias: Optional table alias
        
    Returns:
        Filtered query
    """
    if alias:
        return base_query.filter(alias.project_id == project_id)
    else:
        # Try to detect project_id column
        # This is a simplified version - actual implementation
        # should use proper ORM relationships
        return base_query.filter_by(project_id=project_id)


# Forbidden data patterns for prompt validation
FORBIDDEN_PROMPT_PATTERNS = [
    "full_sitemap",
    "global_keyword_list",
    "all_pages_inventory",
    "competitor_urls",
    "other_client_data",
    "seo_doctrine_rules",
    "other_page_full_content",
    "cross_project",
]


def validate_prompt_isolation(prompt_data: dict, project_id: UUID) -> List[str]:
    """
    Validate that prompt data doesn't contain forbidden cross-project data.
    
    Args:
        prompt_data: Prompt payload dictionary
        project_id: Current project UUID
        
    Returns:
        List of forbidden keys found (empty if valid)
    """
    forbidden_keys = []
    
    # Recursively check for forbidden patterns
    def check_dict(data, path=""):
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                
                # Check if key matches forbidden pattern
                for pattern in FORBIDDEN_PROMPT_PATTERNS:
                    if pattern in key.lower():
                        forbidden_keys.append(current_path)
                
                # Recursively check nested structures
                if isinstance(value, (dict, list)):
                    check_dict(value, current_path)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                check_dict(item, f"{path}[{i}]")
    
    check_dict(prompt_data)
    
    return forbidden_keys
