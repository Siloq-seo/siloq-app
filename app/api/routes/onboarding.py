"""Onboarding questionnaire routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.db.models import Site, SystemEvent
from app.schemas.onboarding import (
    OnboardingQuestionnaire,
    OnboardingQuestionnaireResponse,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/questionnaire", response_model=OnboardingQuestionnaireResponse)
async def submit_onboarding_questionnaire(
    questionnaire: OnboardingQuestionnaire,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit onboarding questionnaire.
    
    The "Dummy-Proof" Input structure that forces users to provide
    data required by Week 5 and Week 3 code.
    
    Sections:
    A. THE WHO (Brand & Compliance) - Brand voice, forbidden words
    B. THE WHAT (Silo Architecture) - Primary service, customer problems
    C. THE WHERE (Entity Injection) - Local landmarks, regional terms
    D. THE WHEN (Risk Assessment) - Site age category
    
    Args:
        questionnaire: Complete onboarding questionnaire
        db: Database session
        
    Returns:
        Response with success status, warnings, and stored data
    """
    warnings = []
    errors = []
    
    # Validate and process questionnaire
    # Check for local details warning (critical)
    if not questionnaire.entity_injection.local_landmarks_neighborhoods or \
       len(questionnaire.entity_injection.local_landmarks_neighborhoods) < 3 or \
       not questionnaire.entity_injection.local_law_regional_term or \
       not questionnaire.entity_injection.local_law_regional_term.strip():
        warnings.append(
            "WARNING: Without local details, ranking potential drops 50%. "
            "Please provide 3 local landmarks/neighborhoods and 1 local law/regional term."
        )
    
    # Get or create site
    site = None
    if questionnaire.site_id:
        site = await db.get(Site, UUID(questionnaire.site_id))
        if not site:
            errors.append(f"Site with ID {questionnaire.site_id} not found")
            return OnboardingQuestionnaireResponse(
                success=False,
                errors=errors,
                message="Site not found",
            )
    else:
        # Create new site (would need domain from somewhere - for now, use name as domain)
        # In a real implementation, domain would be collected separately
        site = Site(
            name=questionnaire.silo_architecture.primary_service_to_rank,
            domain=f"{questionnaire.silo_architecture.primary_service_to_rank.lower().replace(' ', '-')}.com",
        )
        db.add(site)
        await db.commit()
        await db.refresh(site)
    
    # Store questionnaire data in site metadata (or separate table)
    # For now, we'll store it in a JSONB field if available, or create a separate table
    # Since Site model doesn't have metadata field, we'll log it in system_events
    
    # Determine site age category
    site_age_category = questionnaire.risk_assessment.site_age_category
    is_new_site = any(term in site_age_category for term in ["<1", "less than 1", "new"])
    
    # Store onboarding data
    onboarding_data = {
        "brand_compliance": {
            "brand_voice_adjectives": questionnaire.brand_compliance.brand_voice_adjectives,
            "forbidden_words_phrases": questionnaire.brand_compliance.forbidden_words_phrases,
        },
        "silo_architecture": {
            "primary_service_to_rank": questionnaire.silo_architecture.primary_service_to_rank,
            "customer_problems_questions": questionnaire.silo_architecture.customer_problems_questions,
        },
        "entity_injection": {
            "local_landmarks_neighborhoods": questionnaire.entity_injection.local_landmarks_neighborhoods,
            "local_law_regional_term": questionnaire.entity_injection.local_law_regional_term,
        },
        "risk_assessment": {
            "site_age_category": site_age_category,
            "is_new_site": is_new_site,
        },
        "submitted_at": datetime.utcnow().isoformat(),
    }
    
    # Log onboarding submission
    audit = SystemEvent(
        event_type="onboarding_questionnaire_submitted",
        entity_type="site",
        entity_id=site.id,
        payload=onboarding_data,
    )
    db.add(audit)
    await db.commit()
    
    message = "Onboarding questionnaire submitted successfully"
    if warnings:
        message += ". Please review warnings."
    
    return OnboardingQuestionnaireResponse(
        success=True,
        site_id=str(site.id),
        warnings=warnings,
        errors=errors,
        message=message,
        data=onboarding_data,
    )


@router.get("/questionnaire/{site_id}")
async def get_onboarding_questionnaire(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get stored onboarding questionnaire data for a site.
    
    Args:
        site_id: Site UUID
        db: Database session
        
    Returns:
        Stored questionnaire data
    """
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Get onboarding data from system_events
    from sqlalchemy import select
    from app.db.models import SystemEvent
    
    query = (
        select(SystemEvent)
        .where(
            SystemEvent.entity_type == "site",
            SystemEvent.entity_id == site_id,
            SystemEvent.event_type == "onboarding_questionnaire_submitted",
        )
        .order_by(SystemEvent.created_at.desc())
        .limit(1)
    )
    
    result = await db.execute(query)
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Onboarding questionnaire not found for this site"
        )
    
    return {
        "site_id": str(site_id),
        "questionnaire_data": event.payload,
        "submitted_at": event.created_at.isoformat(),
    }

