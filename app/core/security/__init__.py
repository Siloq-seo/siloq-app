"""Security, Privacy & Compliance modules (Section 7)"""
from app.core.security.encryption import (
    EncryptionManager,
    get_encryption_manager,
    APIKeyManager,
    SecurityError,
    validate_api_key_format,
    sanitize_user_input,
)
from app.core.security.rbac import (
    Role,
    has_permission,
    get_user_role,
    require_permission,
    get_minimum_role_for_action,
    get_allowed_actions,
)
from app.core.security.tenant_isolation import (
    get_project_for_site,
    verify_project_access,
    enforce_project_isolation,
    validate_query_scoping,
    detect_cross_project_leak,
    validate_prompt_isolation,
    FORBIDDEN_PROMPT_PATTERNS,
    TenantIsolationError,
)
from app.core.security.kill_switch import KillSwitchManager, get_kill_switch_manager
from app.core.security.audit import AuditLogger, get_audit_logger

__all__ = [
    # Encryption
    "EncryptionManager",
    "get_encryption_manager",
    "APIKeyManager",
    "SecurityError",
    "validate_api_key_format",
    "sanitize_user_input",
    # RBAC
    "Role",
    "has_permission",
    "get_user_role",
    "require_permission",
    "get_minimum_role_for_action",
    "get_allowed_actions",
    # Tenant Isolation
    "get_project_for_site",
    "verify_project_access",
    "enforce_project_isolation",
    "validate_query_scoping",
    "detect_cross_project_leak",
    "validate_prompt_isolation",
    "FORBIDDEN_PROMPT_PATTERNS",
    "TenantIsolationError",
    # Kill Switch
    "KillSwitchManager",
    "get_kill_switch_manager",
    # Audit
    "AuditLogger",
    "get_audit_logger",
]
