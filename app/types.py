"""Type definitions for Siloq - TypedDict classes for type safety"""
from typing import TypedDict, Optional, List, Dict, Any
from uuid import UUID


# ============================================================================
# Governance Types
# ============================================================================

class GateCheckResult(TypedDict, total=False):
    """Result of a single lifecycle gate check"""
    passed: bool
    reason: Optional[str]
    details: Dict[str, Any]


class AllGatesResult(TypedDict, total=False):
    """Result of checking all lifecycle gates"""
    all_gates_passed: bool
    gates: Dict[str, GateCheckResult]
    blocked: bool
    reason: str
    failed_gates: List[str]


class SimilarContentItem(TypedDict):
    """Item in similar content list"""
    id: str
    title: str
    path: str
    similarity: float


class CannibalizationResult(TypedDict, total=False):
    """Result of cannibalization check"""
    is_cannibalized: bool
    similar_content: List[SimilarContentItem]
    max_similarity: float
    threshold: float


class PublishingSafetyResult(TypedDict, total=False):
    """Result of publishing safety check"""
    is_safe: bool
    checks: Dict[str, Any]
    blocked: bool
    reason: str


class RedirectValidationResult(TypedDict, total=False):
    """Result of redirect validation"""
    valid: bool
    is_internal: bool
    target_page_id: Optional[UUID]
    issues: List[str]


class RedirectEnforcementResult(TypedDict, total=False):
    """Result of redirect enforcement"""
    success: bool
    redirect_enforced: bool
    redirect_to: Optional[str]
    is_internal: bool
    target_page_id: Optional[UUID]
    error: Optional[str]


class AuthorityPreservationResult(TypedDict, total=False):
    """Result of authority preservation on decommission"""
    success: bool
    authority_preserved: bool
    authority_data: Dict[str, Any]
    redirect_enforced: bool


class ValidationResult(TypedDict, total=False):
    """General validation result"""
    passed: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

