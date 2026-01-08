"""Entitlement & Plan Enforcement - Section 8"""
from enum import Enum
from typing import Dict, Set, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from uuid import UUID

from app.db.models import (
    ProjectEntitlement, PlanType, Project, MonthlyUsageSummary
)
from app.exceptions import GovernanceError
from app.decision.error_codes import ErrorCode, ErrorCodeDictionary


# Plan definitions
class PlanEntitlements:
    """Plan entitlements configuration"""
    
    TRIAL = {
        "create_project": True,
        "crawl_audit": True,
        "view_governance_dashboard": True,
        "view_reverse_silo_planner": True,
        "view_cannibalization_clusters": True,
        "generate_recommendations": False,
        "draft_generation": False,
        "apply_content": False,
        "publish": False,
        "bulk_actions": False,
        "restoration_mode": False,
        "max_projects": 1,
        "max_concurrent_jobs": 1,
        "max_drafts_per_day": 0,
        "max_drafts_per_month": 0,
    }
    
    BLUEPRINT = {
        **TRIAL,  # Inherit trial
        "generate_recommendations": True,
        "max_projects": 1,
        "draft_generation": False,  # Still blocked
        "apply_content": False,  # Still blocked
    }
    
    OPERATOR = {
        "create_project": True,
        "crawl_audit": True,
        "view_governance_dashboard": True,
        "view_reverse_silo_planner": True,
        "view_cannibalization_clusters": True,
        "generate_recommendations": True,
        "draft_generation": True,
        "apply_content": True,
        "publish": True,
        "bulk_actions": False,
        "restoration_mode": True,
        "compliance_shield": True,
        "radius_guard": True,
        "max_projects": 1,
        "max_concurrent_jobs": 5,
        "max_drafts_per_day": 50,
        "max_drafts_per_month": None,  # Unlimited
    }
    
    AGENCY = {
        **OPERATOR,  # Inherit operator
        "bulk_draft_generation": True,
        "client_segmentation": True,
        "max_projects": 5,
        "max_concurrent_jobs": 10,
        "max_drafts_per_day": 200,
    }
    
    EMPIRE = {
        **AGENCY,  # Inherit agency
        "bulk_publish_scheduled": True,
        "agency_command_center": True,
        "white_label_ui": True,
        "custom_domains": True,
        "sla_governance": True,
        "api_priority_queue": True,
        "sub_accounts": True,
        "max_projects": 20,
        "max_concurrent_jobs": 20,
        "max_drafts_per_day": 500,
    }


# Feature → Plan Matrix (Canonical)
FEATURE_MATRIX: Dict[str, List[str]] = {
    "governance_dashboard": ["trial", "blueprint", "operator", "agency", "empire"],
    "reverse_silo_planner": ["trial", "blueprint", "operator", "agency", "empire"],
    "draft_generation": ["operator", "agency", "empire"],
    "apply_content": ["operator", "agency", "empire"],
    "publish": ["operator", "agency", "empire"],
    "bulk_drafts": ["agency", "empire"],
    "compliance_shield": ["operator", "agency", "empire"],
    "radius_guard": ["operator", "agency", "empire"],
    "white_label": ["empire"],
    "agency_dashboard": ["empire"],
    "api_access": ["empire"],
}


def get_plan_entitlements(plan_key: PlanType) -> Dict:
    """Get entitlements for a plan"""
    plan_map = {
        PlanType.TRIAL: PlanEntitlements.TRIAL,
        PlanType.BLUEPRINT: PlanEntitlements.BLUEPRINT,
        PlanType.OPERATOR: PlanEntitlements.OPERATOR,
        PlanType.AGENCY: PlanEntitlements.AGENCY,
        PlanType.EMPIRE: PlanEntitlements.EMPIRE,
    }
    return plan_map.get(plan_key, PlanEntitlements.TRIAL)


async def get_project_entitlements(project_id: UUID, db: AsyncSession) -> Optional[ProjectEntitlement]:
    """
    Get entitlements for a project.
    
    Args:
        project_id: Project UUID
        db: Database session
        
    Returns:
        ProjectEntitlement or None if not found
    """
    return await db.get(ProjectEntitlement, project_id)


async def has_access(project_id: UUID, feature: str, db: AsyncSession) -> bool:
    """
    Check if project has access to a feature.
    
    Args:
        project_id: Project UUID
        feature: Feature name
        db: Database session
        
    Returns:
        True if project has access
    """
    entitlements = await get_project_entitlements(project_id, db)
    if not entitlements:
        return False
    
    plan_key = entitlements.plan_key.value
    allowed_plans = FEATURE_MATRIX.get(feature, [])
    
    return plan_key in allowed_plans


def get_minimum_plan(feature: str) -> str:
    """
    Get minimum plan required for a feature.
    
    Args:
        feature: Feature name
        
    Returns:
        Minimum plan name (e.g., "operator")
    """
    allowed_plans = FEATURE_MATRIX.get(feature, [])
    
    # Plan order (lowest to highest)
    plan_order = ["trial", "blueprint", "operator", "agency", "empire"]
    
    for plan in plan_order:
        if plan in allowed_plans:
            return plan
    
    return "empire"  # Default to highest if not found


async def require_feature(
    project_id: UUID,
    feature: str,
    db: AsyncSession
) -> ProjectEntitlement:
    """
    Require that a project has access to a feature.
    
    Args:
        project_id: Project UUID
        feature: Required feature
        db: Database session
        
    Returns:
        ProjectEntitlement if access granted
        
    Raises:
        GovernanceError: If access denied
    """
    entitlements = await get_project_entitlements(project_id, db)
    
    if not entitlements:
        error_code = ErrorCode(
            code="ENTITLEMENT_NOT_FOUND",
            message="Project entitlements not found",
            doctrine_reference="Section 8: Entitlement & Plan Enforcement",
            remediation_steps=["Contact support to set up project entitlements"],
            severity="BLOCK"
        )
        raise GovernanceError(error_code, project_id)
    
    if not has_access(project_id, feature, db):
        minimum_plan = get_minimum_plan(feature)
        error_code = ErrorCode(
            code="ENTITLEMENT_REQUIRED",
            message=f"This feature requires {minimum_plan} plan",
            doctrine_reference="Section 8: Entitlement & Plan Enforcement",
            remediation_steps=[
                f"Upgrade to {minimum_plan} plan to access {feature}",
                f"Current plan: {entitlements.plan_key.value}"
            ],
            severity="BLOCK"
        )
        raise GovernanceError(error_code, project_id)
    
    return entitlements


async def check_usage_limits(
    project_id: UUID,
    feature: str,
    db: AsyncSession
) -> bool:
    """
    Check if project has exceeded usage limits.
    
    Args:
        project_id: Project UUID
        feature: Feature name
        db: Database session
        
    Returns:
        True if within limits, False if exceeded
    """
    entitlements = await get_project_entitlements(project_id, db)
    if not entitlements:
        return False
    
    if feature == "draft_generation":
        # Check daily limit
        if entitlements.max_drafts_per_day:
            # Get today's usage
            today = datetime.utcnow().date()
            # TODO: Implement daily usage query
            # For now, assume within limits
            
        # Check monthly limit
        if entitlements.max_drafts_per_month:
            now = datetime.utcnow()
            month_start = datetime(now.year, now.month, 1)
            
            # Get monthly usage summary
            stmt = select(MonthlyUsageSummary).where(
                and_(
                    MonthlyUsageSummary.project_id == project_id,
                    MonthlyUsageSummary.year == now.year,
                    MonthlyUsageSummary.month == now.month
                )
            )
            result = await db.execute(stmt)
            monthly_usage = result.scalar_one_or_none()
            
            if monthly_usage:
                if monthly_usage.total_drafts_generated >= entitlements.max_drafts_per_month:
                    return False
    
    return True


async def check_blueprint_usage(project_id: UUID, db: AsyncSession) -> bool:
    """
    Check if blueprint activation has already been used.
    
    Args:
        project_id: Project UUID
        db: Database session
        
    Returns:
        True if blueprint can be used, False if already used
    """
    entitlements = await get_project_entitlements(project_id, db)
    if not entitlements:
        return False
    
    if entitlements.plan_key == PlanType.BLUEPRINT:
        # Blueprint allows one target page only
        if entitlements.blueprint_target_page_id:
            return False
    
    return True


async def get_current_month_usage(project_id: UUID, db: AsyncSession) -> Dict:
    """
    Get current month's usage for a project.
    
    Args:
        project_id: Project UUID
        db: Database session
        
    Returns:
        Dictionary with usage metrics
    """
    now = datetime.utcnow()
    
    stmt = select(MonthlyUsageSummary).where(
        and_(
            MonthlyUsageSummary.project_id == project_id,
            MonthlyUsageSummary.year == now.year,
            MonthlyUsageSummary.month == now.month
        )
    )
    result = await db.execute(stmt)
    monthly_usage = result.scalar_one_or_none()
    
    if monthly_usage:
        return {
            "drafts_generated": monthly_usage.total_drafts_generated,
            "total_tokens": monthly_usage.total_tokens,
            "total_cost_usd": monthly_usage.total_cost_usd,
            "total_jobs": monthly_usage.total_jobs,
        }
    
    return {
        "drafts_generated": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_jobs": 0,
    }
