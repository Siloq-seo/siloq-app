"""Billing and usage tracking routes"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.db.models import Site, GenerationJob, Page

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)


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
    try:
        # Get all sites (in a real implementation, filter by current_user's account)
        sites_query = select(Site)
        sites_result = await db.execute(sites_query)
        sites = sites_result.scalars().all()
        
        sites_used = len(sites)
        sites_limit = 10  # Default limit, should come from user's plan
        
        # Get content jobs count for this month
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        try:
            jobs_query = select(func.count(GenerationJob.id)).where(
                GenerationJob.created_at >= start_of_month
            )
            jobs_result = await db.execute(jobs_query)
            content_jobs_this_month = jobs_result.scalar() or 0
        except Exception as e:
            logger.warning(f"Could not count jobs: {e}")
            content_jobs_this_month = 0
        
        # Calculate tokens consumed (estimate from job costs since AIUsageLog might not be populated)
        tokens_consumed = 0
        try:
            # Try to get from AIUsageLog if available
            from app.db.models import AIUsageLog
            # Use total_tokens (not tokens_used - that field doesn't exist)
            if hasattr(AIUsageLog, 'total_tokens'):
                tokens_query = select(func.sum(AIUsageLog.total_tokens)).where(
                    AIUsageLog.created_at >= start_of_month
                )
                tokens_result = await db.execute(tokens_query)
                tokens_consumed = tokens_result.scalar() or 0
            else:
                logger.warning("AIUsageLog.total_tokens attribute not found")
                tokens_consumed = 0
        except AttributeError as e:
            logger.warning(f"AIUsageLog model issue: {e}")
            tokens_consumed = 0
        except Exception as e:
            logger.warning(f"Could not query AIUsageLog: {e}")
            tokens_consumed = 0
        
        # If no AIUsageLog entries, estimate from job costs
        if tokens_consumed == 0 or tokens_consumed is None:
            try:
                # Rough estimate: $0.01 per 1000 tokens for GPT-4
                cost_query = select(func.sum(GenerationJob.total_cost_usd)).where(
                    GenerationJob.created_at >= start_of_month
                )
                cost_result = await db.execute(cost_query)
                total_cost = cost_result.scalar() or 0.0
                tokens_consumed = int(total_cost * 100000)  # Rough estimate
            except Exception as e:
                logger.warning(f"Could not estimate tokens from costs: {e}")
                tokens_consumed = 0
        
        # Calculate cost breakdown by site
        cost_by_site = {}
        cost_by_job_type = {}
        
        try:
            for site in sites:
                try:
                    # Join GenerationJob with Page to get costs per site
                    site_jobs_query = select(func.sum(GenerationJob.total_cost_usd)).select_from(
                        GenerationJob
                    ).join(
                        Page, GenerationJob.page_id == Page.id
                    ).where(
                        Page.site_id == site.id,
                        GenerationJob.created_at >= start_of_month
                    )
                    site_cost_result = await db.execute(site_jobs_query)
                    site_cost = site_cost_result.scalar() or 0.0
                    cost_by_site[str(site.id)] = round(site_cost, 2)
                except Exception as e:
                    logger.warning(f"Could not calculate cost for site {site.id}: {e}")
                    # If join fails or no pages exist, set cost to 0
                    cost_by_site[str(site.id)] = 0.0
            
            # Job type breakdown (for now, all are "content_generation")
            total_cost = sum(cost_by_site.values()) if cost_by_site else 0.0
            cost_by_job_type["content_generation"] = round(total_cost, 2)
        except Exception as e:
            logger.warning(f"Error calculating cost breakdown: {e}")
            # If there's any error in cost calculation, return empty breakdowns
            cost_by_site = {}
            cost_by_job_type = {"content_generation": 0.0}
        
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
    except Exception as e:
        logger.error(f"Error in get_billing_usage: {e}", exc_info=True)
        # Return a safe default response instead of crashing
        return {
            "plan": "Operator",
            "sitesUsed": 0,
            "sitesLimit": 10,
            "tokensConsumed": 0,
            "contentJobsThisMonth": 0,
            "costBreakdown": {
                "bySite": {},
                "byJobType": {"content_generation": 0.0},
            },
        }
