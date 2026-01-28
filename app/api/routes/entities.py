"""Entity management and coverage routes"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from uuid import UUID
from typing import Optional
from collections import defaultdict

from app.core.database import get_db
from app.core.auth import get_current_user
from app.db.models import Page, Site, Silo

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("")
async def list_entities(
    siteId: Optional[UUID] = Query(None, alias="siteId", description="Filter by site ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all entities across sites.
    
    Args:
        siteId: Optional site ID to filter entities
        
    Returns:
        List of entities with their associated pages
    """
    # Build query for pages
    query = select(Page)
    if siteId:
        query = query.where(Page.site_id == siteId)
    
    result = await db.execute(query)
    pages = result.scalars().all()
    
    # Extract entities from pages
    # Entities are stored in structured_output_metadata or governance_checks
    entities_map = defaultdict(lambda: {
        "id": None,
        "name": None,
        "type": "service",  # Default type
        "pages": [],
        "coverageScore": 0,
    })
    
    for page in pages:
        # Try to get entities from structured_output_metadata (from generation jobs)
        # or from governance_checks
        entities = []
        
        # Check if page has generation jobs with structured output
        from app.db.models import GenerationJob
        jobs_query = select(GenerationJob).where(GenerationJob.page_id == page.id)
        jobs_result = await db.execute(jobs_query)
        jobs = jobs_result.scalars().all()
        
        for job in jobs:
            if job.structured_output_metadata and "entities" in job.structured_output_metadata:
                entities.extend(job.structured_output_metadata["entities"])
        
        # Also check governance_checks
        if page.governance_checks and "entities" in page.governance_checks:
            entities.extend(page.governance_checks["entities"])
        
        # Process entities
        for entity_data in entities:
            if isinstance(entity_data, dict):
                entity_name = entity_data.get("name") or entity_data.get("entity") or str(entity_data)
                entity_type = entity_data.get("type", "service")
            else:
                entity_name = str(entity_data)
                entity_type = "service"
            
            entity_key = entity_name.lower()
            if entity_key not in entities_map:
                entities_map[entity_key] = {
                    "id": entity_key,
                    "name": entity_name,
                    "type": entity_type,
                    "pages": [],
                    "coverageScore": 0,
                }
            
            entities_map[entity_key]["pages"].append(str(page.id))
    
    # Calculate coverage scores
    total_pages = len(pages)
    for entity in entities_map.values():
        if total_pages > 0:
            entity["coverageScore"] = min(100, int((len(entity["pages"]) / total_pages) * 100))
    
    return list(entities_map.values())


@router.get("/coverage")
async def get_entity_coverage(
    siteId: Optional[UUID] = Query(None, alias="siteId", description="Filter by site ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get entity coverage analysis across sites.
    
    Args:
        siteId: Optional site ID to filter coverage
        
    Returns:
        List of entity coverage data with gaps analysis
    """
    # Get entities
    entities_query = select(Page)
    if siteId:
        entities_query = entities_query.where(Page.site_id == siteId)
    
    entities_result = await db.execute(entities_query)
    pages = entities_result.scalars().all()
    
    # Get all sites
    sites_query = select(Site)
    if siteId:
        sites_query = sites_query.where(Site.id == siteId)
    
    sites_result = await db.execute(sites_query)
    sites = sites_result.scalars().all()
    
    # Extract entities and their coverage
    entities_map = defaultdict(lambda: {
        "entity": None,
        "sites": set(),
        "totalPages": 0,
        "coveragePercentage": 0,
        "gaps": [],
    })
    
    # Track which sites have which entities
    site_entities = defaultdict(set)
    
    for page in pages:
        site = await db.get(Site, page.site_id)
        site_id_str = str(page.site_id)
        
        # Extract entities from page
        entities = []
        
        # Check generation jobs
        from app.db.models import GenerationJob
        jobs_query = select(GenerationJob).where(GenerationJob.page_id == page.id)
        jobs_result = await db.execute(jobs_query)
        jobs = jobs_result.scalars().all()
        
        for job in jobs:
            if job.structured_output_metadata and "entities" in job.structured_output_metadata:
                entities.extend(job.structured_output_metadata["entities"])
        
        # Check governance_checks
        if page.governance_checks and "entities" in page.governance_checks:
            entities.extend(page.governance_checks["entities"])
        
        # Process entities
        for entity_data in entities:
            if isinstance(entity_data, dict):
                entity_name = entity_data.get("name") or entity_data.get("entity") or str(entity_data)
            else:
                entity_name = str(entity_data)
            
            entity_key = entity_name.lower()
            entities_map[entity_key]["entity"] = {
                "id": entity_key,
                "name": entity_name,
                "type": entity_data.get("type", "service") if isinstance(entity_data, dict) else "service",
                "pages": entities_map[entity_key].get("pages", []) + [str(page.id)],
                "coverageScore": 0,
            }
            entities_map[entity_key]["sites"].add(site_id_str)
            entities_map[entity_key]["totalPages"] += 1
            site_entities[site_id_str].add(entity_key)
    
    # Calculate coverage and gaps
    total_sites = len(sites)
    coverage_list = []
    
    for entity_key, entity_data in entities_map.items():
        sites_with_entity = len(entity_data["sites"])
        coverage_percentage = (sites_with_entity / total_sites * 100) if total_sites > 0 else 0
        
        # Identify gaps (sites without this entity)
        gaps = []
        for site in sites:
            site_id_str = str(site.id)
            if entity_key not in site_entities[site_id_str]:
                gaps.append(site.name or site.domain)
        
        coverage_list.append({
            "entity": entity_data["entity"],
            "sites": list(entity_data["sites"]),
            "totalPages": entity_data["totalPages"],
            "coveragePercentage": round(coverage_percentage, 2),
            "gaps": gaps,
        })
    
    return coverage_list
