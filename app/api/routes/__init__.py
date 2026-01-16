"""API route modules"""
from app.api.routes.sites import router as sites_router
from app.api.routes.pages import router as pages_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.silos import router as silos_router
from app.api.routes.onboarding import router as onboarding_router
from app.api.routes.wordpress import router as wordpress_router

__all__ = ["sites_router", "pages_router", "jobs_router", "silos_router", "onboarding_router", "wordpress_router"]

