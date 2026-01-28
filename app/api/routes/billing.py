"""Billing and usage tracking routes"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.auth import get_current_user
from app.db.models import Site, GenerationJob, Page, AIUsageLog

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/usage")
async def get_billing_usage(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get billing usage statistics.
    
    Returns:
        Billing usage data including plan, sites used, tokens consumed, and cost breakdown
    """
    # Get all sites (in a real implementation, filter by current_user's account)
    sites_query = select(Site)
    sites_result = await db.execute(sites_query)
    sites = sites_result.scalars().all()
    
    sites_used = len(sites)
    sites_limit = 10  # Default limit, should come from user's plan
    
    # Get content jobs count for this month
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    jobs_query = select(func.count(GenerationJob.id)).where(
        GenerationJob.created_at >= start_of_month
    )
    jobs_result = await db.execute(jobs_query)
    content_jobs_this_month = jobs_result.scalar() or 0
    
    # Calculate tokens consumed (from AIUsageLog if available, otherwise estimate from jobs)
    tokens_query = select(func.sum(AIUsageLog.tokens_used)).where(
        AIUsageLog.created_at >= start_of_month
    )
    tokens_result = await db.execute(tokens_query)
    tokens_consumed = tokens_result.scalar() or 0
    
    # If no AIUsageLog entries, estimate from job costs
    if tokens_consumed == 0:
        # Rough estimate: $0.01 per 1000 tokens for GPT-4
        cost_query = select(func.sum(GenerationJob.total_cost_usd)).where(
            GenerationJob.created_at >= start_of_month
        )
        cost_result = await db.execute(cost_query)
        total_cost = cost_result.scalar() or 0.0
        tokens_consumed = int(total_cost * 100000)  # Rough estimate
    
    # Calculate cost breakdown by site
    cost_by_site = {}
    cost_by_job_type = {}
    
    for site in sites:
        site_jobs_query = select(func.sum(GenerationJob.total_cost_usd)).join(Page).where(
            Page.site_id == site.id,
            GenerationJob.created_at >= start_of_month
        )
        site_cost_result = await db.execute(site_jobs_query)
        site_cost = site_cost_result.scalar() or 0.0
        cost_by_site[str(site.id)] = round(site_cost, 2)
    
    # Job type breakdown (for now, all are "content_generation")
    cost_by_job_type["content_generation"] = round(
        sum(cost_by_site.values()), 2
    )
    
    # Determine plan based on usage (simplified logic)
    if sites_used <= 3:
        plan = "Operator"
    elif sites_used <= 10:
        plan = "Architect"
    else:
        plan = "Empire"
    
    return {
        "plan": plan,
        "sitesUsed": sites_used,
        "sitesLimit": sites_limit,
        "tokensConsumed": tokens_consumed,
        "contentJobsThisMonth": content_jobs_this_month,
        "costBreakdown": {
            "bySite": cost_by_site,
            "byJobType": cost_by_job_type,
        },
    }
