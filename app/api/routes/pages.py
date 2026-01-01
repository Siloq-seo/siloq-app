"""Page management and lifecycle routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.db.models import Page, ContentStatus, GenerationJob, SystemEvent
from app.api.dependencies import (
    get_lifecycle_gate_manager,
    get_publishing_safety,
    get_jsonld_generator,
    get_preflight_validator,
    get_postcheck_validator,
    get_near_duplicate_detector,
)
from app.schemas.pages import (
    PageCreate,
    PageResponse,
    GateCheckResponse,
    DecommissionRequest,
)
from app.decision.schemas import ValidationPayload, ValidationResult
from app.decision.state_machine import StateMachineManager, JobState
from app.decision.event_logger import EventLogger
from app.decision.error_codes import ErrorCodeDictionary
from app.exceptions import LifecycleGateError, PublishingError, DecommissionError
from app.queues.queue_manager import queue_manager

router = APIRouter(prefix="/pages", tags=["pages"])


@router.get("/{page_id}", response_model=PageResponse)
async def get_page(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get page details by ID.
    
    Args:
        page_id: Page UUID
        db: Database session
        
    Returns:
        Page data
        
    Raises:
        HTTPException: 404 if page not found
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/{page_id}/jsonld")
async def get_page_jsonld(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    jsonld_generator = Depends(get_jsonld_generator),
):
    """
    Get JSON-LD schema for a page.
    
    Args:
        page_id: Page UUID
        db: Database session
        jsonld_generator: JSON-LD generator service
        
    Returns:
        JSON-LD schema object
        
    Raises:
        HTTPException: 404 if page not found
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    schema = await jsonld_generator.generate_schema(db, page)
    return schema


@router.get("/{page_id}/gates", response_model=GateCheckResponse)
async def check_publish_gates(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    gate_manager = Depends(get_lifecycle_gate_manager),
):
    """
    Check all lifecycle gates for a page without publishing.
    
    Returns gate status for all gates:
    1. Governance checks gate
    2. Schema sync validation gate
    3. Embedding gate
    4. Authority gate
    5. Content structure gate
    6. Status gate
    7. Experience verification gate (2025 SEO)
    8. GEO formatting gate (2025 SEO)
    9. Core Web Vitals gate (2025 SEO)
    
    Args:
        page_id: Page UUID
        db: Database session
        gate_manager: Lifecycle gate manager service
        
    Returns:
        Gate check results with detailed status for each gate
        
    Raises:
        HTTPException: 404 if page not found
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    gates_result = await gate_manager.check_all_gates(db, page)
    await db.commit()
    
    return gates_result


@router.post("/{page_id}/publish")
async def publish_page(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    gate_manager = Depends(get_lifecycle_gate_manager),
):
    """
    Publish page with all lifecycle gates.
    
    All gates must pass:
    1. Governance checks gate
    2. Schema sync validation gate
    3. Embedding gate
    4. Authority gate
    5. Content structure gate
    6. Status gate
    7. Experience verification gate (2025 SEO)
    8. GEO formatting gate (2025 SEO)
    9. Core Web Vitals gate (2025 SEO)
    
    Unsafe content cannot ship.
    
    Args:
        page_id: Page UUID
        db: Database session
        gate_manager: Lifecycle gate manager service
        
    Returns:
        Success response with published_at timestamp
        
    Raises:
        LifecycleGateError: If any gate fails
        HTTPException: 404 if page not found
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Check all lifecycle gates
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
        elif "experience" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_008
        elif "geo_formatting" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_009
        elif "web_vitals" in failed_gates:
            error_code = ErrorCodeDictionary.LIFECYCLE_010
        
        raise LifecycleGateError(
            error_code=error_code or ErrorCodeDictionary.LIFECYCLE_001,
            entity_id=page_id,
            context={
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


@router.post("/{page_id}/decommission")
async def decommission_page(
    page_id: UUID,
    request: DecommissionRequest,
    db: AsyncSession = Depends(get_db),
    publishing_safety = Depends(get_publishing_safety),
):
    """
    Decommission page while preserving authority and enforcing redirects.
    
    Ensures:
    - Authority score is preserved
    - Source URLs are maintained
    - Redirect is validated and enforced (if provided)
    - All changes are logged
    
    Args:
        page_id: Page UUID
        request: Decommission request with optional redirect
        db: Database session
        publishing_safety: Publishing safety service
        
    Returns:
        Success response with authority preservation data
        
    Raises:
        DecommissionError: If redirect validation fails
        HTTPException: 404 if page not found
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Decommission with redirect enforcement
    result = await publishing_safety.preserve_authority_on_decommission(
        db, page, request.redirect_to
    )

    if not result.get("success"):
        error_code = ErrorCodeDictionary.LIFECYCLE_007
        raise DecommissionError(
            error_code=error_code,
            entity_id=page_id,
            context={"redirect_result": result},
        )

    return result


@router.post("/{page_id}/validate", response_model=ValidationResult)
async def validate_page(
    page_id: UUID,
    payload: ValidationPayload,
    db: AsyncSession = Depends(get_db),
    preflight_validator = Depends(get_preflight_validator),
):
    """
    Validate page before generation (preflight check).
    
    This endpoint:
    1. Runs all preflight validation checks
    2. Returns validation result with error codes if failed
    3. Updates job state to PREFLIGHT_APPROVED on success
    4. Logs validation attempt for audit trail
    
    Args:
        page_id: Page UUID
        payload: Validation payload
        db: Database session
        preflight_validator: Preflight validator service
        
    Returns:
        Validation result with passed status and errors/warnings
        
    Raises:
        HTTPException: 404 if page not found, 400 if page_id mismatch
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


@router.post("/{page_id}/check-similarity")
async def check_similarity(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    detector = Depends(get_near_duplicate_detector),
):
    """
    Check similarity before generation (requires embedding).
    
    Args:
        page_id: Page UUID
        db: Database session
        detector: Near duplicate detector service
        
    Returns:
        Similarity detection results
        
    Raises:
        HTTPException: 404 if page not found, 400 if embedding missing
    """
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    if not page.embedding:
        raise HTTPException(
            status_code=400, detail="Page must have embedding for similarity check"
        )
    
    detection_result = await detector.detect_near_duplicates(
        db, page_id, page.embedding, page.site_id
    )
    
    return detection_result.to_dict()


@router.post("/{page_id}/postcheck")
async def postcheck_validation(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    postcheck_validator = Depends(get_postcheck_validator),
):
    """
    Run post-generation validation with full embedding checks.
    
    Args:
        page_id: Page UUID
        db: Database session
        postcheck_validator: Postcheck validator service
        
    Returns:
        Postcheck validation results
        
    Raises:
        HTTPException: 404 if page not found, 400 if embedding missing
    """
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
    
    return validation_result

