"""API layer - Routes, dependencies, and exception handlers"""
from app.api.routes import (
    sites_router,
    pages_router,
    jobs_router,
    silos_router,
    onboarding_router,
    api_keys_router,
    scans_router,
    wordpress_router,
)
from app.api.dependencies import (
    get_lifecycle_gate_manager,
    get_publishing_safety,
    get_jsonld_generator,
    get_preflight_validator,
    get_postcheck_validator,
    get_near_duplicate_detector,
    verify_site_access,
    verify_page_access,
)
from app.api.exception_handlers import (
    governance_error_handler,
    validation_error_handler,
    publishing_error_handler,
    decommission_error_handler,
    cannibalization_error_handler,
    lifecycle_gate_error_handler,
    validation_exception_handler,
    integrity_error_handler,
)

__all__ = [
    # Routers
    "sites_router",
    "pages_router",
    "jobs_router",
    "silos_router",
    "onboarding_router",
    "api_keys_router",
    "scans_router",
    "wordpress_router",
    # Dependencies
    "get_lifecycle_gate_manager",
    "get_publishing_safety",
    "get_jsonld_generator",
    "get_preflight_validator",
    "get_postcheck_validator",
    "get_near_duplicate_detector",
    "verify_site_access",
    "verify_page_access",
    # Exception Handlers
    "governance_error_handler",
    "validation_error_handler",
    "publishing_error_handler",
    "decommission_error_handler",
    "cannibalization_error_handler",
    "lifecycle_gate_error_handler",
    "validation_exception_handler",
    "integrity_error_handler",
]
