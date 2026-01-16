"""Role-Based Access Control (RBAC) middleware and permissions"""
from enum import Enum
from typing import List, Optional, Dict, Set
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.db.models import User, Project


class Role(str, Enum):
    """User roles"""
    OWNER = "owner"     # Full control including billing
    ADMIN = "admin"     # Content + users, no billing
    EDITOR = "editor"   # Content only
    VIEWER = "viewer"   # Read-only


# Permission definitions
PERMISSIONS: Dict[Role, Set[str]] = {
    Role.OWNER: {
        "project.delete",
        "billing.update",
        "api_keys.manage",
        "users.manage",
        "content.*",
        "drafts.generate",
        "drafts.apply",
        "publish.approve",
        "links.manage",
    },
    Role.ADMIN: {
        "users.manage",
        "content.*",
        "drafts.generate",
        "drafts.apply",
        "publish.approve",
        "links.manage",
    },
    Role.EDITOR: {
        "content.create",
        "content.edit",
        "content.read",
        "drafts.generate",
        "drafts.apply",
    },
    Role.VIEWER: {
        "content.read",
        "metrics.view",
    },
}


def has_permission(role: Role, action: str) -> bool:
    """
    Check if a role has permission for an action.
    
    Args:
        role: User role
        action: Action to check (supports wildcards, e.g., "content.*")
        
    Returns:
        True if role has permission
    """
    permissions = PERMISSIONS.get(role, set())
    
    # Direct match
    if action in permissions:
        return True
    
    # Wildcard match (e.g., "content.*" matches "content.create")
    for perm in permissions:
        if perm.endswith(".*"):
            prefix = perm[:-2]  # Remove ".*"
            if action.startswith(prefix + ".") or action == prefix:
                return True
    
    return False


async def get_user_role(user_id: UUID, project_id: UUID, db: AsyncSession) -> Optional[Role]:
    """
    Get user's role for a specific project.
    
    Args:
        user_id: User UUID
        project_id: Project UUID
        db: Database session
        
    Returns:
        User role or None if user doesn't have access to project
    """
    # Get user
    user = await db.get(User, user_id)
    if not user or user.deleted_at is not None:
        return None
    
    # Get project and verify user's organization has access
    project = await db.get(Project, project_id)
    if not project or project.deleted_at is not None:
        return None
    
    # Check if user's organization owns the project
    if user.organization_id != project.organization_id:
        return None
    
    # Return user's role (in future, we might have project-specific roles)
    try:
        return Role(user.role)
    except ValueError:
        return None


async def require_permission(
    user_id: UUID,
    project_id: UUID,
    action: str,
    db: AsyncSession
) -> Role:
    """
    Require that a user has a specific permission for a project.
    
    Args:
        user_id: User UUID
        project_id: Project UUID
        action: Required action
        db: Database session
        
    Returns:
        User role if permission granted
        
    Raises:
        HTTPException: If permission denied
    """
    role = await get_user_role(user_id, project_id, db)
    
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": "User does not have access to this project",
                "remediation": "Contact your organization administrator for access"
            }
        )
    
    if not has_permission(role, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": f"User role '{role.value}' does not have permission for '{action}'",
                "remediation": f"Required role: {get_minimum_role_for_action(action)} or higher",
                "current_role": role.value,
                "required_action": action
            }
        )
    
    return role


def get_minimum_role_for_action(action: str) -> str:
    """
    Get the minimum role required for an action.
    
    Args:
        action: Action to check
        
    Returns:
        Minimum required role name
    """
    # Check roles in order of authority
    roles_order = [Role.VIEWER, Role.EDITOR, Role.ADMIN, Role.OWNER]
    
    for role in roles_order:
        if has_permission(role, action):
            return role.value
    
    return "owner"  # Default to most restrictive


def get_allowed_actions(role: Role) -> List[str]:
    """
    Get all allowed actions for a role.
    
    Args:
        role: User role
        
    Returns:
        List of allowed action strings
    """
    permissions = PERMISSIONS.get(role, set())
    return sorted(list(permissions))
