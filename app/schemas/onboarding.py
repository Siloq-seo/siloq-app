"""
Onboarding Questionnaire Schemas

The "Dummy-Proof" Input structure for plugin onboarding wizard.
Forces users to provide data required by Week 5 and Week 3 code.
"""
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator


class ContentScope(str, Enum):
    """Content scope: Local (service-based) or National (e-commerce)"""
    LOCAL = "local"
    NATIONAL = "national"


class BrandVoice(str, Enum):
    """Standardized brand voice options"""
    VOICE_EXPERT = "voice_expert"  # Authoritative, Technical
    VOICE_NEIGHBOR = "voice_neighbor"  # Warm, "You/We" language, Local
    VOICE_HYPE = "voice_hype"  # Energetic, Sales-focused


class BrandComplianceInput(BaseModel):
    """A. THE WHO (Brand & Compliance)"""
    brand_voice: BrandVoice = Field(
        ...,
        description="Brand voice style (dropdown selection)"
    )
    forbidden_words_phrases: List[str] = Field(
        default=[],
        description="Forbidden words/phrases (Legal/Compliance)"
    )


class SiloArchitectureInput(BaseModel):
    """B. THE WHAT (Silo Architecture)"""
    primary_service_to_rank: str = Field(
        ...,
        min_length=10,
        description="Primary Service to Rank (Target Page). Must be specific, not generic."
    )
    customer_problems_questions: List[str] = Field(
        ...,
        min_items=5,
        max_items=5,
        description="5 Specific Customer Problems/Questions (Supporting Blogs)"
    )
    
    @validator("primary_service_to_rank")
    def validate_primary_service(cls, v):
        """Block generic one-word answers."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Primary service must be at least 10 characters and specific")
        
        # Block generic answers
        generic_answers = ["service", "product", "solution", "help", "support"]
        v_lower = v.lower()
        if any(generic in v_lower for generic in generic_answers) and len(v.split()) < 3:
            raise ValueError("Primary service is too generic. Be specific (e.g., 'Plumbing Repair Services in Downtown Seattle' not just 'Plumbing')")
        
        return v
    
    @validator("customer_problems_questions")
    def validate_customer_problems(cls, v):
        """Ensure problems/questions are specific."""
        if len(v) != 5:
            raise ValueError("Must provide exactly 5 customer problems/questions")
        
        for i, problem in enumerate(v, 1):
            problem = problem.strip()
            if len(problem) < 15:
                raise ValueError(f"Problem/Question {i} is too short. Must be at least 15 characters and specific.")
            
            # Block generic questions
            generic_patterns = ["how to", "what is", "why", "when"]
            problem_lower = problem.lower()
            if any(pattern in problem_lower for pattern in generic_patterns) and len(problem.split()) < 5:
                raise ValueError(f"Problem/Question {i} is too generic. Be specific (e.g., 'How do I fix a leaking pipe under my kitchen sink?' not just 'How to fix pipes?')")
        
        return v


class EntityInjectionInput(BaseModel):
    """C. THE WHERE (Entity Injection - Critical)"""
    scope: ContentScope = Field(
        ...,
        description="Content scope: Local (service-based) or National (e-commerce)"
    )
    local_landmarks_neighborhoods: Optional[List[str]] = Field(
        None,
        min_items=3,
        max_items=3,
        description="List 3 specific local landmarks/neighborhoods (required if scope=local)"
    )
    local_law_regional_term: Optional[str] = Field(
        None,
        min_length=5,
        description="List 1 local law or regional term (required if scope=local)"
    )
    
    @root_validator(skip_on_failure=True)
    def validate_scope_requirements(cls, values):
        """Validate requirements based on scope."""
        scope = values.get("scope")
        landmarks = values.get("local_landmarks_neighborhoods", [])
        law_term = values.get("local_law_regional_term", "")
        
        if scope == ContentScope.LOCAL:
            # Local scope requires landmarks and regional term
            if not landmarks or len(landmarks) < 3:
                raise ValueError("Local scope requires 3 local landmarks/neighborhoods")
            if not law_term or not law_term.strip():
                raise ValueError("Local scope requires 1 local law or regional term")
            
            # Validate landmark quality
            for i, landmark in enumerate(landmarks, 1):
                landmark = landmark.strip()
                if not landmark or len(landmark) < 5:
                    raise ValueError(f"Landmark/Neighborhood {i} is too short. Must be specific (e.g., 'Pike Place Market' not 'Market')")
        elif scope == ContentScope.NATIONAL:
            # National scope should not have local landmarks
            if landmarks:
                raise ValueError("National scope cannot have local landmarks. Remove landmarks for national content.")
            if law_term:
                raise ValueError("National scope cannot have local law/regional term. Remove for national content.")
        
        return values


class RiskAssessmentInput(BaseModel):
    """D. THE WHEN (Risk Assessment)"""
    site_age_category: str = Field(
        ...,
        description="Is the site <1 year old or >1 year old?"
    )
    
    @validator("site_age_category")
    def validate_site_age(cls, v):
        """Validate site age category."""
        v_lower = v.lower().strip()
        valid_categories = ["<1 year", "< 1 year", "less than 1 year", "new", "new site", ">1 year", "> 1 year", "more than 1 year", "established", "established site"]
        
        if v_lower not in valid_categories:
            raise ValueError(
                f"Site age category must be one of: '<1 year' or '>1 year'. "
                f"Received: '{v}'"
            )
        
        return v_lower


class OnboardingQuestionnaire(BaseModel):
    """Complete onboarding questionnaire."""
    brand_compliance: BrandComplianceInput = Field(..., description="A. THE WHO (Brand & Compliance)")
    silo_architecture: SiloArchitectureInput = Field(..., description="B. THE WHAT (Silo Architecture)")
    entity_injection: EntityInjectionInput = Field(..., description="C. THE WHERE (Entity Injection)")
    risk_assessment: RiskAssessmentInput = Field(..., description="D. THE WHEN (Risk Assessment)")
    site_id: Optional[str] = Field(None, description="Optional site ID if updating existing site")
    
    @root_validator(skip_on_failure=True)
    def validate_scope_consistency(cls, values):
        """Validate scope consistency across questionnaire."""
        entity_injection = values.get("entity_injection")
        
        if entity_injection and entity_injection.scope == ContentScope.LOCAL:
            # Local scope: Show warning if local details missing
            landmarks = entity_injection.local_landmarks_neighborhoods
            law_term = entity_injection.local_law_regional_term
            
            if not landmarks or len(landmarks) < 3 or not law_term or not law_term.strip():
                # This will be handled in the API to show warning
                pass
        
        return values


class OnboardingQuestionnaireResponse(BaseModel):
    """Response from onboarding questionnaire submission."""
    success: bool
    site_id: Optional[str] = None
    warnings: List[str] = []
    errors: List[str] = []
    message: str
    data: Optional[dict] = None

