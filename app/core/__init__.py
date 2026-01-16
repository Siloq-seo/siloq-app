"""Core configuration and utilities"""

# Re-export commonly used modules for backward compatibility
from app.core.config import settings
from app.core.database import get_db, engine, Base
from app.core.auth import get_current_user, create_access_token, decode_access_token
from app.core.redis import redis_client
from app.core.rate_limit import RateLimitMiddleware

# Security modules (Section 7)
from app.core.security import (
    EncryptionManager,
    get_encryption_manager,
    APIKeyManager,
    Role,
    has_permission,
    get_user_role,
    require_permission,
    get_minimum_role_for_action,
    get_allowed_actions,
    get_project_for_site,
    verify_project_access,
    enforce_project_isolation,
    validate_query_scoping,
    detect_cross_project_leak,
    validate_prompt_isolation,
    FORBIDDEN_PROMPT_PATTERNS,
    TenantIsolationError,
    KillSwitchManager,
    get_kill_switch_manager,
    AuditLogger,
    get_audit_logger,
    SecurityError,
)

# Billing modules (Section 8)
from app.core.billing import (
    PlanEntitlements,
    FEATURE_MATRIX,
    get_plan_entitlements,
    get_project_entitlements,
    has_access,
    get_minimum_plan,
    require_feature,
    check_usage_limits,
    check_blueprint_usage,
    get_current_month_usage,
)

__all__ = [
    # Config & Infrastructure
    "settings",
    "get_db",
    "engine",
    "Base",
    "get_current_user",
    "create_access_token",
    "decode_access_token",
    "redis_client",
    "RateLimitMiddleware",
    # Security
    "EncryptionManager",
    "get_encryption_manager",
    "APIKeyManager",
    "Role",
    "has_permission",
    "get_user_role",
    "require_permission",
    "get_minimum_role_for_action",
    "get_allowed_actions",
    "get_project_for_site",
    "verify_project_access",
    "enforce_project_isolation",
    "validate_query_scoping",
    "detect_cross_project_leak",
    "validate_prompt_isolation",
    "FORBIDDEN_PROMPT_PATTERNS",
    "TenantIsolationError",
    "KillSwitchManager",
    "get_kill_switch_manager",
    "AuditLogger",
    "get_audit_logger",
    "SecurityError",
    # Billing
    "PlanEntitlements",
    "FEATURE_MATRIX",
    "get_plan_entitlements",
    "get_project_entitlements",
    "has_access",
    "get_minimum_plan",
    "require_feature",
    "check_usage_limits",
    "check_blueprint_usage",
    "get_current_month_usage",
]