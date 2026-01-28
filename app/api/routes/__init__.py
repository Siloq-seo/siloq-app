"""API route modules"""
from app.api.routes.auth import router as auth_router
from app.api.routes.sites import router as sites_router
from app.api.routes.pages import router as pages_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.silos import router as silos_router
from app.api.routes.onboarding import router as onboarding_router
from app.api.routes.wordpress import router as wordpress_router
from app.api.routes.api_keys import router as api_keys_router
from app.api.routes.scans import router as scans_router
from app.api.routes.content_jobs import router as content_jobs_router
from app.api.routes.billing import router as billing_router
from app.api.routes.entities import router as entities_router
from app.api.routes.restoration import router as restoration_router
from app.api.routes.events import router as events_router

__all__ = [
    "auth_router", "sites_router", "pages_router", "jobs_router", "silos_router",
    "onboarding_router", "wordpress_router", "api_keys_router", "scans_router",
    "content_jobs_router", "billing_router", "entities_router", "restoration_router", "events_router"
]

