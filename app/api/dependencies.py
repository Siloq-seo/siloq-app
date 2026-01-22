"""FastAPI dependency injection for Siloq services"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.governance.lifecycle.lifecycle_gates import LifecycleGateManager
from app.governance.content.publishing import PublishingSafety
from app.governance.structure.reverse_silos import ReverseSiloEnforcer
from app.schemas.jsonld import JSONLDGenerator
from app.decision.preflight_validator import PreflightValidator
from app.decision.postcheck_validator import PostCheckValidator
from app.governance.content.near_duplicate_detector import NearDuplicateDetector
from app.governance.sync.reservation_system import ReservationSystem
from app.governance.structure.clusters import ClusterManager
from app.governance.structure.silo_recommendations import SiloRecommendationEngine
from app.governance.structure.silo_finalization import SiloFinalizer
from app.governance.authority.anchor_governance import AnchorGovernor


# Database dependency (already exists, re-export for clarity)
def get_database() -> AsyncSession:
    """Get database session"""
    return Depends(get_db)


# Governance Services
def get_lifecycle_gate_manager() -> LifecycleGateManager:
    """Get lifecycle gate manager instance"""
    return LifecycleGateManager()


def get_publishing_safety() -> PublishingSafety:
    """Get publishing safety instance"""
    return PublishingSafety()


def get_silo_enforcer() -> ReverseSiloEnforcer:
    """Get reverse silo enforcer instance"""
    return ReverseSiloEnforcer()


def get_jsonld_generator() -> JSONLDGenerator:
    """Get JSON-LD generator instance"""
    return JSONLDGenerator()


# Decision Engine Services
def get_preflight_validator() -> PreflightValidator:
    """Get preflight validator instance"""
    return PreflightValidator()


def get_postcheck_validator() -> PostCheckValidator:
    """Get postcheck validator instance"""
    return PostCheckValidator()


# Week 3: Vector Logic Services
def get_near_duplicate_detector() -> NearDuplicateDetector:
    """Get near duplicate detector instance"""
    return NearDuplicateDetector()


def get_reservation_system() -> ReservationSystem:
    """Get reservation system instance"""
    return ReservationSystem()


# Week 4: Reverse Silo Engine Services
def get_cluster_manager() -> ClusterManager:
    """Get cluster manager instance"""
    return ClusterManager()


def get_silo_recommendation_engine() -> SiloRecommendationEngine:
    """Get silo recommendation engine instance"""
    return SiloRecommendationEngine()


def get_silo_finalizer() -> SiloFinalizer:
    """Get silo finalizer instance"""
    return SiloFinalizer()


def get_anchor_governor() -> AnchorGovernor:
    """Get anchor governor instance"""
    return AnchorGovernor()

