"""FastAPI routes for Siloq governance engine"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.db.models import Site, Silo, Page, ContentStatus, GenerationJob, PageSilo
from app.api.dependencies import (
    get_lifecycle_gate_manager,
    get_publishing_safety,
    get_silo_enforcer,
    get_jsonld_generator,
    get_preflight_validator,
    get_postcheck_validator,
    get_near_duplicate_detector,
    get_reservation_system,
    get_cluster_manager,
    get_silo_recommendation_engine,
    get_silo_finalizer,
    get_anchor_governor,
)
from app.queues.queue_manager import queue_manager
from app.schemas.pages import (
    PageCreate,
    PageResponse,
    PageUpdate,
    PublishRequest,
    DecommissionRequest,
    GateCheckResponse,
)
from app.schemas.sites import SiteCreate, SiteResponse, SiloCreate, SiloResponse
from app.schemas.jobs import JobResponse, JobStatusResponse

# Week 2: Decision Engine imports
from app.decision.state_machine import StateMachine, StateMachineManager, JobState
from app.decision.schemas import (
    ValidationPayload,
    ValidationResult,
    StateTransitionRequest,
    StateTransitionResponse,
)
from app.decision.event_logger import EventLogger
from app.decision.error_codes import ErrorCodeDictionary
from app.exceptions import GovernanceError, PublishingError, DecommissionError, LifecycleGateError

# Week 3: Vector Logic imports
from app.governance.geo_exceptions import GeoException
from app.db.models import ContentReservation

# Week 4: Reverse Silo Engine imports
from app.governance.authority_funnel import AuthorityFunnel
from app.db.models import Cluster, ClusterPage, AnchorLink


router = APIRouter()


# Site endpoints
@router.post("/sites", status_code=status.HTTP_201_CREATED, response_model=SiteResponse)
async def create_site(
    site_data: SiteCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new site"""
    site = Site(name=site_data.name, domain=site_data.domain)
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site


@router.get("/sites/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get site details"""
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# Silo endpoints
@router.post("/sites/{site_id}/silos", status_code=status.HTTP_201_CREATED)
async def create_silo(
    site_id: UUID,
    silo_data: SiloCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new silo with structure validation"""
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    silo, success, message = await silo_enforcer.create_silo(
        db, str(site_id), silo_data.name, silo_data.slug
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return silo


@router.get("/sites/{site_id}/silos")
async def get_silos(site_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all silos for a site"""
    silos = await silo_enforcer.get_silos_for_site(db, str(site_id))
    return silos


@router.get("/sites/{site_id}/silos/validate")
async def validate_silo_structure(site_id: UUID, db: AsyncSession = Depends(get_db)):
    """Validate silo structure (3-7 silos)"""
    is_valid, message = await silo_enforcer.validate_silo_structure(db, str(site_id))
    return {"is_valid": is_valid, "message": message}


# Week 2: Decision Engine endpoints
@router.post("/pages/{page_id}/validate", response_model=ValidationResult)
async def validate_page(
    page_id: UUID,
    payload: ValidationPayload,
    db: AsyncSession = Depends(get_db),
    preflight_validator: PreflightValidator = Depends(get_preflight_validator),
):
    """
    Validate page before generation (preflight check).
    
    This endpoint:
    1. Runs all preflight validation checks
    2. Returns validation result with error codes if failed
    3. Updates job state to PREFLIGHT_APPROVED on success
    4. Logs validation attempt for audit trail
    """
    # Verify page exists
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Ensure payload page_id matches URL
    if payload.page_id != page_id:
        raise HTTPException(
            status_code=400, detail="Page ID in payload must match URL parameter"
        )
    
    # Run preflight validation
    validation_result = await preflight_validator.validate(db, payload)
    
    # Log validation attempt
    await EventLogger.log_preflight_result(
        db,
        page_id,
        validation_result.passed,
        validation_result.errors,
        validation_result.warnings,
    )
    
    # If validation passed, update job state to PREFLIGHT_APPROVED
    if validation_result.passed:
        # Find or create generation job for this page
        query = select(GenerationJob).where(GenerationJob.page_id == page_id)
        result = await db.execute(query)
        job = result.scalar_one_or_none()
        
        if job:
            # Transition to PREFLIGHT_APPROVED
            success, error, state_machine = await StateMachineManager.transition_job_state(
                db,
                job.id,
                JobState.PREFLIGHT_APPROVED,
                reason="Preflight validation passed",
            )
            
            if success and state_machine:
                job.preflight_approved_at = datetime.utcnow()
                await db.commit()
                
                # Log state transition
                if state_machine.transition_history:
                    await EventLogger.log_state_transition(
                        db, job.id, state_machine.transition_history[-1]
                    )
    
    return validation_result


@router.post("/jobs/{job_id}/transition", response_model=StateTransitionResponse)
async def transition_job_state(
    job_id: UUID,
    request: StateTransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Transition job to a new state.
    
    This endpoint enforces state machine rules and prevents invalid transitions.
    """
    # Get current state machine
    state_machine = await StateMachineManager.get_state_machine(db, job_id)
    if not state_machine:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Parse target state
    try:
        target_state = JobState(request.target_state.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {request.target_state}",
        )
    
    # Attempt transition
    success, error, updated_state_machine = await StateMachineManager.transition_job_state(
        db,
        job_id,
        target_state,
        reason=request.reason,
        error_code=request.error_code,
    )
    
    if not success:
        error_dict = {
            "code": error.code,
            "message": error.message,
            "doctrine_reference": error.doctrine_reference,
            "remediation_steps": error.remediation_steps,
        }
        return StateTransitionResponse(
            success=False,
            current_state=state_machine.current_state.value,
            error=error_dict,
            allowed_transitions=[
                state.value for state in state_machine.get_allowed_transitions()
            ],
        )
    
    # Log state transition
    if updated_state_machine and updated_state_machine.transition_history:
        await EventLogger.log_state_transition(
            db, job_id, updated_state_machine.transition_history[-1]
        )
    
    return StateTransitionResponse(
        success=True,
        current_state=updated_state_machine.current_state.value,
        previous_state=state_machine.current_state.value,
        allowed_transitions=[
            state.value
            for state in updated_state_machine.get_allowed_transitions()
        ],
    )


@router.get("/pages/{page_id}/validation-history")
async def get_validation_history(
    page_id: UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get validation history for a page."""
    history = await EventLogger.get_validation_history(db, page_id, limit)
    return {"page_id": str(page_id), "history": history}


@router.get("/jobs/{job_id}/state-history")
async def get_state_history(
    job_id: UUID,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get state transition history for a job."""
    history = await EventLogger.get_state_transition_history(db, job_id, limit)
    return {"job_id": str(job_id), "history": history}


# Week 3: Vector Logic & Cannibalization endpoints
@router.post("/pages/{page_id}/check-similarity")
async def check_similarity(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check similarity before generation (requires embedding)."""
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    if not page.embedding:
        raise HTTPException(
            status_code=400, detail="Page must have embedding for similarity check"
        )
    
    detector = NearDuplicateDetector()
    detection_result = await detector.detect_near_duplicates(
        db, page_id, page.embedding, page.site_id
    )
    
    return detection_result.to_dict()


@router.post("/pages/{page_id}/postcheck")
async def postcheck_validation(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Run post-generation validation with full embedding checks."""
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    if not page.embedding:
        raise HTTPException(
            status_code=400, detail="Page must have embedding for post-check"
        )
    
    validation_result = await postcheck_validator.validate(
        db, page_id, page.embedding
    )
    
    # Update job state based on result
    if validation_result.passed:
        query = select(GenerationJob).where(GenerationJob.page_id == page_id)
        result = await db.execute(query)
        job = result.scalar_one_or_none()
        
        if job:
            success, error, state_machine = await StateMachineManager.transition_job_state(
                db,
                job.id,
                JobState.POSTCHECK_PASSED,
                reason="Post-check validation passed",
            )
            if success:
                await db.commit()
    
    return validation_result


@router.post("/reservations")
async def create_reservation(
    site_id: UUID,
    title: str,
    location: Optional[str] = None,
    expiration_days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Create content slot reservation."""
    reservation, success, message = await reservation_system.reserve_content_slot(
        db, site_id, title, location, expiration_days
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return reservation.to_dict()


@router.get("/reservations/{reservation_id}")
async def get_reservation(
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get reservation status."""
    reservation = await db.get(ContentReservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    return {
        "id": str(reservation.id),
        "site_id": str(reservation.site_id),
        "intent_hash": reservation.intent_hash,
        "location": reservation.location,
        "expires_at": reservation.expires_at.isoformat(),
        "is_expired": datetime.utcnow() > reservation.expires_at,
        "fulfilled": reservation.fulfilled_at is not None,
    }


@router.delete("/reservations/{reservation_id}")
async def release_reservation(
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Release content reservation."""
    success, message = await reservation_system.release_reservation(
        db, reservation_id
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


# Week 4: Reverse Silo Engine endpoints
@router.get("/reverse-silos")
async def get_reverse_silos(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all reverse silos for a site with authority funnel data."""
    silos = await reverse_silo_enforcer.get_silos_for_site(db, str(site_id))
    
    silo_data = []
    for silo in silos:
        # Get authority funnel score
        authority_score = await AuthorityFunnel.calculate_silo_authority(db, silo.id)
        
        # Get entity inheritance
        inheritance = await AuthorityFunnel.get_entity_inheritance(db, silo.id)
        
        # Get page count
        from sqlalchemy import func
        page_count_query = select(func.count(PageSilo.id)).where(PageSilo.silo_id == silo.id)
        page_result = await db.execute(page_count_query)
        page_count = page_result.scalar() or 0
        
        silo_data.append({
            "id": str(silo.id),
            "name": silo.name,
            "slug": silo.slug,
            "position": silo.position,
            "is_finalized": silo.is_finalized,
            "finalized_at": silo.finalized_at.isoformat() if silo.finalized_at else None,
            "entity_type": silo.entity_type,
            "parent_silo_id": str(silo.parent_silo_id) if silo.parent_silo_id else None,
            "authority_funnel_score": authority_score,
            "entity_inheritance": inheritance,
            "page_count": page_count,
            "anchor_governance_enabled": silo.anchor_governance_enabled,
        })
    
    return {"site_id": str(site_id), "silos": silo_data}


@router.post("/reverse-silos")
async def create_reverse_silo(
    site_id: UUID,
    name: str,
    slug: str,
    entity_type: Optional[str] = None,
    parent_silo_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a new reverse silo."""
    silo, success, message = await reverse_silo_enforcer.create_silo(
        db, str(site_id), name, slug
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Update entity type and parent if provided
    if entity_type:
        silo.entity_type = entity_type
    if parent_silo_id:
        silo.parent_silo_id = parent_silo_id
    
    await db.commit()
    await db.refresh(silo)
    
    return {
        "id": str(silo.id),
        "name": silo.name,
        "slug": silo.slug,
        "position": silo.position,
        "entity_type": silo.entity_type,
        "parent_silo_id": str(silo.parent_silo_id) if silo.parent_silo_id else None,
    }


@router.post("/recommendations:generate")
async def generate_recommendations(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate silo recommendations based on content clusters."""
    recommendations = await recommendation_engine.generate_recommendations(db, site_id)
    return recommendations


@router.post("/silos/{silo_id}/finalize")
async def finalize_silo(
    silo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Finalize a silo structure."""
    success, message, data = await silo_finalizer.finalize_silo(db, silo_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message,
        "data": data,
    }


@router.get("/silos/{silo_id}/finalization-status")
async def get_finalization_status(
    silo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get finalization status for a silo."""
    status = await silo_finalizer.get_finalization_status(db, silo_id)
    return status


@router.post("/anchor-links")
async def create_anchor_link(
    from_page_id: UUID,
    to_page_id: UUID,
    anchor_text: str,
    authority_passed: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a governed anchor link."""
    success, message, anchor_link = await anchor_governor.create_anchor_link(
        db, from_page_id, to_page_id, anchor_text, authority_passed
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "id": str(anchor_link.id),
        "from_page_id": str(anchor_link.from_page_id),
        "to_page_id": str(anchor_link.to_page_id),
        "anchor_text": anchor_link.anchor_text,
        "authority_passed": anchor_link.authority_passed,
        "silo_id": str(anchor_link.silo_id) if anchor_link.silo_id else None,
    }


@router.get("/pages/{page_id}/anchor-links")
async def get_page_anchor_links(
    page_id: UUID,
    direction: str = "both",  # 'outbound', 'inbound', 'both'
    db: AsyncSession = Depends(get_db),
):
    """Get anchor links for a page."""
    links = await anchor_governor.get_anchor_links_for_page(db, page_id, direction)
    return {"page_id": str(page_id), "direction": direction, "links": links}


@router.post("/clusters")
async def create_cluster(
    site_id: UUID,
    name: str,
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a content cluster."""
    cluster = await cluster_manager.create_cluster(db, site_id, name, description)
    return cluster.to_dict()


@router.post("/clusters/{cluster_id}/pages")
async def add_page_to_cluster(
    cluster_id: UUID,
    page_id: UUID,
    role: str = "member",
    db: AsyncSession = Depends(get_db),
):
    """Add a page to a cluster."""
    success = await cluster_manager.add_page_to_cluster(db, cluster_id, page_id, role)
    return {"success": success}


@router.post("/silos/{silo_id}/supporting-pages")
async def add_supporting_page(
    silo_id: UUID,
    page_id: UUID,
    supporting_role: str = "pillar",
    authority_weight: float = 1.0,
    db: AsyncSession = Depends(get_db),
):
    """Add a supporting page to a silo."""
    from app.db.models import PageSilo
    
    # Check if already exists
    query = select(PageSilo).where(
        and_(
            PageSilo.silo_id == silo_id,
            PageSilo.page_id == page_id,
        )
    )
    result = await db.execute(query)
    page_silo = result.scalar_one_or_none()
    
    if page_silo:
        page_silo.is_supporting_page = True
        page_silo.supporting_role = supporting_role
        page_silo.authority_weight = authority_weight
    else:
        page_silo = PageSilo(
            silo_id=silo_id,
            page_id=page_id,
            is_supporting_page=True,
            supporting_role=supporting_role,
            authority_weight=authority_weight,
        )
        db.add(page_silo)
    
    await db.commit()
    await db.refresh(page_silo)
    
    return {
        "success": True,
        "page_silo_id": str(page_silo.id),
        "is_supporting_page": page_silo.is_supporting_page,
        "supporting_role": page_silo.supporting_role,
        "authority_weight": page_silo.authority_weight,
    }


# Content endpoints (keeping existing for backward compatibility)
@router.post("/contents", status_code=status.HTTP_201_CREATED)
async def create_content(
    content_data: ContentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create content and queue generation job"""
    # Verify site exists
    site = await db.get(Site, content_data.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Verify silo if provided
    if content_data.silo_id:
        silo = await db.get(Silo, content_data.silo_id)
        if not silo:
            raise HTTPException(status_code=404, detail="Silo not found")

    # Create content record
    content = Page(
        site_id=content_data.site_id,
        title=content_data.title,
        path=f"/{content_data.slug}",
        body="",  # Will be generated
        status=ContentStatus.DRAFT,
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)

    # Create generation job record
    job = GenerationJob(
        page_id=content.id,
        job_id="",  # Will be set by queue
        status="draft",
    )
    db.add(job)
    await db.commit()

    # Add job to queue
    job_id = await queue_manager.add_generation_job(
        content_id=str(content.id),
        title=content_data.title,
        slug=content_data.slug,
        site_id=str(content_data.site_id),
        silo_id=str(content_data.silo_id) if content_data.silo_id else None,
        prompt=content_data.prompt,
        metadata=content_data.metadata,
    )

    # Update job with queue job_id
    job.job_id = job_id
    await db.commit()

    return {
        "content_id": content.id,
        "job_id": job_id,
        "status": "queued",
    }


@router.get("/pages/{page_id}")
async def get_page(page_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get page details"""
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/pages/{page_id}/jsonld")
async def get_page_jsonld(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    jsonld_generator: JSONLDGenerator = Depends(get_jsonld_generator),
):
    """Get JSON-LD schema for page"""
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    schema = await jsonld_generator.generate_schema(db, page)
    return schema


@router.get("/pages/{page_id}/gates", response_model=GateCheckResponse)
async def check_publish_gates(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    gate_manager: LifecycleGateManager = Depends(get_lifecycle_gate_manager),
):
    """
    Week 6: Check all lifecycle gates for a page without publishing.
    
    Returns gate status for all 6 gates:
    1. Governance checks gate
    2. Schema sync validation gate
    3. Embedding gate
    4. Authority gate
    5. Content structure gate
    6. Status gate
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    gates_result = await gate_manager.check_all_gates(db, page)
    await db.commit()
    
    return gates_result


@router.post("/pages/{page_id}/publish")
async def publish_page(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    gate_manager: LifecycleGateManager = Depends(get_lifecycle_gate_manager),
):
    """
    Week 6: Publish page with all lifecycle gates.
    
    All gates must pass:
    1. Governance checks gate
    2. Schema sync validation gate
    3. Embedding gate
    4. Authority gate
    5. Content structure gate
    6. Status gate
    
    Unsafe content cannot ship.
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Week 6: Check all lifecycle gates
    gates_result = await gate_manager.check_all_gates(db, page)

    if not gates_result["all_gates_passed"]:
        # Get error code for first failed gate
        failed_gates = gates_result.get("failed_gates", [])
        error_code = None
        
        if "governance" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_001
        elif "schema_sync" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_002
        elif "embedding" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_003
        elif "authority" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_004
        elif "structure" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_005
        elif "status" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_006
        
        error_dict = error_code.to_dict() if error_code else {
            "code": "LIFECYCLE_GATES_FAILED",
            "message": gates_result.get("reason", "One or more lifecycle gates failed"),
        }
        
        raise HTTPException(
            status_code=400,
            detail={
                "error": error_dict,
                "gates": gates_result.get("gates", {}),
                "failed_gates": failed_gates,
            },
        )

    # All gates passed - publish
    page.status = ContentStatus.PUBLISHED
    page.published_at = datetime.utcnow()
    
    # Update governance_checks with publish info
    if not page.governance_checks:
        page.governance_checks = {}
    page.governance_checks["published"] = {
        "published_at": page.published_at.isoformat(),
        "all_gates_passed": True,
    }
    
    # Log publish event
    from app.db.models import SystemEvent
    audit = SystemEvent(
        event_type="page_published",
        entity_type="page",
        entity_id=page.id,
        payload={
            "published_at": page.published_at.isoformat(),
            "all_gates_passed": True,
            "gates": gates_result.get("gates", {}),
        },
    )
    db.add(audit)
    
    await db.commit()

    return {
        "success": True,
        "page_id": str(page_id),
        "status": "published",
        "published_at": page.published_at.isoformat(),
        "all_gates_passed": True,
    }


@router.post("/pages/{page_id}/decommission")
async def decommission_page(
    page_id: UUID,
    request: DecommissionRequest,
    db: AsyncSession = Depends(get_db),
    publishing_safety: PublishingSafety = Depends(get_publishing_safety),
):
    """
    Week 6: Decommission page while preserving authority and enforcing redirects.
    
    Ensures:
    - Authority score is preserved
    - Source URLs are maintained
    - Redirect is validated and enforced (if provided)
    - All changes are logged
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Week 6: Decommission with redirect enforcement
    result = await publishing_safety.preserve_authority_on_decommission(
        db, page, request.redirect_to
    )

    if not result.get("success"):
        error_code = ErrorCodeDictionary.LIFECYCLE_007
        raise HTTPException(
            status_code=400,
            detail={
                "error": error_code.to_dict(),
                "redirect_result": result,
            },
        )

    return result


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    status = await queue_manager.get_job_status(job_id)
    return status
