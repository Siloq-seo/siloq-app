"""Pydantic schemas for API requests and responses"""
# Import all schemas for easy access
from app.schemas.jobs import JobResponse, JobStatusResponse
from app.schemas.jsonld import JSONLDGenerator
from app.schemas.onboarding import (
    OnboardingQuestionnaire,
    OnboardingQuestionnaireResponse,
    BrandComplianceInput,
    SiloArchitectureInput,
    EntityInjectionInput,
    RiskAssessmentInput,
    ContentScope,
    BrandVoice,
)
from app.schemas.pages import (
    PageResponse,
    PageCreate,
    PageUpdate,
    PublishRequest,
    DecommissionRequest,
    GateCheckResponse,
)
from app.schemas.scans import ScanRequest, ScanResponse, ScanSummary, Recommendation
from app.schemas.sites import SiteResponse, SiteCreate, SiloCreate, SiloResponse

__all__ = [
    # Jobs
    "JobResponse",
    "JobStatusResponse",
    # JSON-LD
    "JSONLDGenerator",
    # Onboarding
    "OnboardingQuestionnaire",
    "OnboardingQuestionnaireResponse",
    "BrandComplianceInput",
    "SiloArchitectureInput",
    "EntityInjectionInput",
    "RiskAssessmentInput",
    "ContentScope",
    "BrandVoice",
    # Pages
    "PageResponse",
    "PageCreate",
    "PageUpdate",
    "PublishRequest",
    "DecommissionRequest",
    "GateCheckResponse",
    # Scans
    "ScanRequest",
    "ScanResponse",
    "ScanSummary",
    "Recommendation",
    # Sites
    "SiteResponse",
    "SiteCreate",
    "SiloCreate",
    "SiloResponse",
]
