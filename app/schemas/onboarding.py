"""
Onboarding Questionnaire Schemas

The "Dummy-Proof" Input structure for plugin onboarding wizard.
Forces users to provide data required by Week 5 and Week 3 code.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, validator, root_validator


class BrandComplianceInput(BaseModel):
    """A. THE WHO (Brand & Compliance)"""
    brand_voice_adjectives: List[str] = Field(
        ...,
        min_items=3,
        max_items=3,
        description="Describe brand voice (exactly 3 adjectives)"
    )
    forbidden_words_phrases: List[str] = Field(
        default=[],
        description="Forbidden words/phrases (Legal/Compliance)"
    )
    
    @validator("brand_voice_adjectives")
    def validate_brand_voice(cls, v):
        """Ensure adjectives are not empty or generic."""
        if len(v) != 3:
            raise ValueError("Must provide exactly 3 brand voice adjectives")
        
        # Block generic one-word answers
        generic_words = ["good", "great", "nice", "best", "top", "quality", "professional"]
        for adj in v:
            adj_lower = adj.lower().strip()
            if not adj_lower or len(adj_lower) < 3:
                raise ValueError(f"Adjective '{adj}' is too short or empty")
            if adj_lower in generic_words:
                raise ValueError(f"Adjective '{adj}' is too generic. Be more specific.")
        
        return v


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
    local_landmarks_neighborhoods: List[str] = Field(
        ...,
        min_items=3,
        max_items=3,
        description="List 3 specific local landmarks/neighborhoods"
    )
    local_law_regional_term: str = Field(
        ...,
        min_length=5,
        description="List 1 local law or regional term"
    )
    
    @validator("local_landmarks_neighborhoods")
    def validate_landmarks(cls, v):
        """Ensure landmarks are specific."""
        if len(v) != 3:
            raise ValueError("Must provide exactly 3 local landmarks/neighborhoods")
        
        for i, landmark in enumerate(v, 1):
            landmark = landmark.strip()
            if not landmark or len(landmark) < 5:
                raise ValueError(f"Landmark/Neighborhood {i} is too short. Must be specific (e.g., 'Pike Place Market' not 'Market')")
        
        return v
    
    @root_validator
    def validate_local_details_warning(cls, values):
        """Show warning if local details are missing."""
        landmarks = values.get("local_landmarks_neighborhoods", [])
        law_term = values.get("local_law_regional_term", "")
        
        if not landmarks or len(landmarks) < 3 or not law_term:
            # This validation will show warning but not block
            # The warning message will be shown in the API response
            pass
        
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
    
    @root_validator
    def validate_local_details_warning(cls, values):
        """Show warning if local details are missing (critical for ranking)."""
        entity_injection = values.get("entity_injection")
        
        if entity_injection:
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

