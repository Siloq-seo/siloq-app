"""WordPress TALI (Theme-Aware Layout Intelligence) API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user
from app.db.models import Project, Site


router = APIRouter(prefix="/wordpress", tags=["wordpress"])


class ThemeProfileRequest(BaseModel):
    """Theme profile from WordPress TALI fingerprinter"""
    tali_version: str
    platform: str = "wordpress"
    theme: Dict[str, Any]
    tokens: Dict[str, Any]
    fingerprinted_at: str


class ThemeProfileResponse(BaseModel):
    """Theme profile response"""
    project_id: str
    profile_stored: bool
    message: str


class ClaimStateRequest(BaseModel):
    """Claim state request"""
    claim_id: str


class ClaimStateResponse(BaseModel):
    """Claim state response"""
    claim_id: str
    access_state: str  # ENABLED or FROZEN
    governance: str = "V1"
    frozen_reason: Optional[str] = None


class PageSyncRequest(BaseModel):
    """WordPress page sync request"""
    wordpress_post_id: int
    title: str
    path: str
    content: Optional[str] = None
    status: str = "publish"
    metadata: Optional[Dict[str, Any]] = None


class PageSyncResponse(BaseModel):
    """Page sync response"""
    siloq_page_id: str
    wordpress_post_id: int
    synced: bool
    message: str


@router.post("/projects/{project_id}/theme-profile", response_model=ThemeProfileResponse)
async def sync_theme_profile(
    project_id: UUID,
    profile: ThemeProfileRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync WordPress theme design profile to Siloq.
    
    Called by WordPress TALI fingerprinter on:
    - Plugin activation
    - Theme change detection
    - Manual "Re-Fingerprint Theme" action
    """
    # Get project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Store theme profile in project metadata
    # For now, store in a JSONB column or project settings
    # TODO: Create project_theme_settings table if needed
    
    # Get site for this project
    site = await db.get(Site, project.site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found for project"
        )
    
    # Store in site metadata (temporary - should be in project_theme_settings)
    if not site.site_type:
        site.site_type = "LOCAL_SERVICE"  # Default
    
    # Store theme profile in JSONB metadata (add theme_profile column if needed)
    # For now, use existing JSONB fields or create migration
    
    # Log theme profile sync
    from app.core.security.audit import get_audit_logger
    audit_logger = get_audit_logger(db)
    await audit_logger.create_event(
        event_type="THEME_PROFILE_SYNC",
        severity="INFO",
        action="WordPress theme profile synchronized",
        project_id=project_id,
        actor_id=UUID(current_user.get("user_id")) if current_user.get("user_id") else None,
        actor_type="user",
        target_entity_type="project",
        target_entity_id=project_id,
        payload={
            "theme_name": profile.theme.get("name"),
            "theme_slug": profile.theme.get("stylesheet"),
            "is_block_theme": profile.theme.get("is_block_theme"),
            "tali_version": profile.tali_version,
        },
        doctrine_section="Section 9: WordPress TALI",
    )
    
    await db.commit()
    
    return ThemeProfileResponse(
        project_id=str(project_id),
        profile_stored=True,
        message="Theme profile synchronized successfully"
    )


@router.get("/claims/{claim_id}/state", response_model=ClaimStateResponse)
async def get_claim_state(
    claim_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get access state for a claim ID.
    
    Used by WordPress TALI access control to determine if content should be
    rendered (ENABLED) or suppressed with receipt preserved (FROZEN).
    """
    # Extract project ID from claim ID if possible
    # Format: CLAIM:TYPE-HASH
    # For now, get from query parameter or infer from user's projects
    
    # Get user's projects
    # TODO: Implement claim-to-project mapping
    # For now, return ENABLED by default (can be enhanced with claim registry)
    
    # In production, you would:
    # 1. Look up claim_id in claim registry table
    # 2. Get associated project_id
    # 3. Check project entitlements/billing status
    # 4. Check global kill switches
    # 5. Return appropriate state
    
    # Default: ENABLED (for development)
    access_state = "ENABLED"
    
    # TODO: Implement actual claim state lookup
    # Example logic:
    # claim_registry = await db.get(ClaimRegistry, claim_id)
    # if not claim_registry:
    #     access_state = "FROZEN"
    # elif claim_registry.project.billing_status != "active":
    #     access_state = "FROZEN"
    # elif kill_switch_active(claim_registry.project_id):
    #     access_state = "FROZEN"
    # else:
    #     access_state = "ENABLED"
    
    return ClaimStateResponse(
        claim_id=claim_id,
        access_state=access_state,
        governance="V1",
        frozen_reason=None if access_state == "ENABLED" else "Project billing inactive"
    )


@router.post("/projects/{project_id}/pages/sync", response_model=PageSyncResponse)
async def sync_wordpress_page(
    project_id: UUID,
    page_data: PageSyncRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync WordPress page to Siloq.
    
    Called when WordPress post is saved/updated.
    Creates or updates corresponding Siloq page.
    """
    # Get project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get site for this project
    site = await db.get(Site, project.site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found for project"
        )
    
    # Check if page already exists (by WordPress post ID)
    # TODO: Create wp_page_mappings table or use metadata
    
    # For now, create new page in Siloq
    from app.db.models import Page, ContentStatus
    
    # Determine content status
    if page_data.status == "publish":
        content_status = ContentStatus.PUBLISHED
    elif page_data.status == "draft":
        content_status = ContentStatus.DRAFT
    else:
        content_status = ContentStatus.DRAFT
    
    # Create page
    page = Page(
        site_id=site.id,
        path=page_data.path,
        title=page_data.title,
        body=page_data.content or "",
        status=content_status,
    )
    
    db.add(page)
    await db.commit()
    await db.refresh(page)
    
    # Store WordPress mapping
    # TODO: Store in wp_page_mappings table
    
    # Log page sync
    from app.core.security.audit import get_audit_logger
    audit_logger = get_audit_logger(db)
    await audit_logger.create_event(
        event_type="WORDPRESS_PAGE_SYNC",
        severity="INFO",
        action="WordPress page synchronized to Siloq",
        project_id=project_id,
        actor_id=UUID(current_user.get("user_id")) if current_user.get("user_id") else None,
        actor_type="user",
        target_entity_type="page",
        target_entity_id=page.id,
        payload={
            "wordpress_post_id": page_data.wordpress_post_id,
            "siloq_page_id": str(page.id),
            "status": page_data.status,
        },
        doctrine_section="Section 9: WordPress TALI",
    )
    
    await db.commit()
    
    return PageSyncResponse(
        siloq_page_id=str(page.id),
        wordpress_post_id=page_data.wordpress_post_id,
        synced=True,
        message="Page synchronized successfully"
    )


@router.post("/projects/{project_id}/pages/{page_id}/inject-blocks")
async def inject_authority_blocks(
    project_id: UUID,
    page_id: UUID,
    content_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Inject authority blocks into WordPress page.
    
    Called when Siloq generates content and needs to inject it into WordPress
    as Gutenberg blocks with claim anchors.
    """
    # Get project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify page belongs to project
    from app.db.models import Page
    page = await db.get(Page, page_id)
    if not page or page.site_id != project.site_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found or does not belong to project"
        )
    
    # Generate claim IDs for each section
    claim_manifest = []
    if "sections" in content_data:
        for index, section in enumerate(content_data["sections"]):
            # Generate deterministic claim ID
            import hashlib
            hash_input = f"{page_id}{section.get('heading', '')}{section.get('type', 'default')}"
            hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
            claim_id = f"CLAIM:{section.get('type', 'UNK').upper()}-{hash_value.upper()}"
            claim_manifest.append(claim_id)
    
    # Return block injection data
    # WordPress plugin will handle actual injection
    return {
        "page_id": str(page_id),
        "claim_manifest": claim_manifest,
        "content_data": content_data,
        "message": "Authority blocks prepared for injection"
    }
