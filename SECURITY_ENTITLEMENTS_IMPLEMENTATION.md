# Security, Privacy & Compliance + Entitlement & Plan Enforcement Implementation

## Overview

This document summarizes the implementation of **Section 7 (Security, Privacy & Compliance)** and **Section 8 (Entitlement & Plan Enforcement)** from the Complete Master Specification.

## Implementation Status

### ✅ Completed Modules

#### 1. Database Schema (V012 Migration)
**File**: `migrations/V012__security_entitlements_system.sql`

- ✅ **Users & Organizations**: Tenant hierarchy (Organizations → Users → Projects)
- ✅ **Projects**: Tenant isolation boundary (1:1 with Sites for backward compatibility)
- ✅ **Project Entitlements**: Plan definitions (trial, blueprint, operator, agency, empire)
- ✅ **Project AI Settings**: BYOK (Bring Your Own Key) with encrypted API keys
- ✅ **Enhanced System Events**: Immutable audit logging with comprehensive fields
- ✅ **Usage Tracking**: AI usage logs and monthly usage summaries
- ✅ **Indexes**: Optimized indexes for tenant isolation and audit queries
- ✅ **Constraints**: Immutability triggers for system_events

#### 2. Database Models
**File**: `app/db/models.py`

New models added:
- ✅ `Organization`: Top-level tenant boundary
- ✅ `User`: Authentication and RBAC (owner, admin, editor, viewer)
- ✅ `Project`: Tenant isolation boundary (maps to Sites)
- ✅ `ProjectEntitlement`: Plan entitlements and feature access
- ✅ `ProjectAISettings`: BYOK settings with encrypted API keys
- ✅ `SystemEvent` (Enhanced): Immutable audit logging with actor tracking
- ✅ `AIUsageLog`: Token usage and cost tracking
- ✅ `MonthlyUsageSummary`: Aggregated monthly usage per project

#### 3. Security Module
**File**: `app/core/security.py`

- ✅ **EncryptionManager**: AES-256-GCM encryption with project-specific key derivation
- ✅ **APIKeyManager**: BYOK encryption/decryption and masking utilities
- ✅ **validate_api_key_format**: Provider-specific API key validation
- ✅ **sanitize_user_input**: XSS prevention for user inputs
- ✅ **Payload hashing**: SHA-256 hashing for integrity verification

#### 4. RBAC (Role-Based Access Control)
**File**: `app/core/rbac.py`

- ✅ **Role enum**: owner, admin, editor, viewer
- ✅ **Permission definitions**: Granular permissions per role
- ✅ **has_permission**: Permission checking with wildcard support
- ✅ **get_user_role**: Project-scoped role lookup
- ✅ **require_permission**: Permission enforcement with HTTP exceptions
- ✅ **get_minimum_role_for_action**: Minimum role calculation

#### 5. Entitlement & Plan Enforcement
**File**: `app/core/entitlements.py`

- ✅ **Plan definitions**: Complete plan entitlements (trial, blueprint, operator, agency, empire)
- ✅ **Feature matrix**: Feature → Plan mapping
- ✅ **get_project_entitlements**: Entitlement lookup
- ✅ **has_access**: Feature access checking
- ✅ **require_feature**: Feature enforcement with GovernanceError
- ✅ **check_usage_limits**: Daily/monthly usage limit validation
- ✅ **check_blueprint_usage**: Blueprint activation usage tracking
- ✅ **get_current_month_usage**: Monthly usage metrics

#### 6. Enhanced Audit Logging
**File**: `app/core/audit.py`

- ✅ **AuditLogger**: Immutable audit log manager
- ✅ **create_event**: Generic event logging with payload hashing
- ✅ **log_validation_run**: Preflight validation logging
- ✅ **log_generation_attempt**: AI generation logging
- ✅ **log_content_applied**: Content application logging
- ✅ **log_page_published**: Publishing event logging
- ✅ **log_permission_change**: RBAC change logging
- ✅ **log_entitlement_check**: Entitlement check logging
- ✅ **query_events**: Read-only event queries with filtering

#### 7. Tenant Isolation
**File**: `app/core/tenant_isolation.py`

- ✅ **get_project_for_site**: Project lookup from site
- ✅ **verify_project_access**: Organization-scoped project access verification
- ✅ **enforce_project_isolation**: Hard tenant isolation enforcement
- ✅ **validate_query_scoping**: SQL query project_id filter validation (safeguard)
- ✅ **detect_cross_project_leak**: Cross-project context leak detection
- ✅ **validate_prompt_isolation**: Prompt data validation for forbidden patterns
- ✅ **FORBIDDEN_PROMPT_PATTERNS**: List of forbidden prompt data patterns

#### 8. Kill Switch Functionality
**File**: `app/core/kill_switch.py`

- ✅ **KillSwitchManager**: Global, project, and user-level kill switches
- ✅ **check_generation_allowed**: Multi-level generation permission check
- ✅ **set_project_kill_switch**: Project-level kill switch control
- ✅ **set_user_kill_switch**: User-level kill switch control
- ✅ **get_global_kill_switch_status**: Global kill switch status from config

#### 9. Error Codes
**File**: `app/decision/error_codes.py`

New error codes added:
- ✅ `ENTITLEMENT_REQUIRED`: Feature requires paid plan
- ✅ `PLAN_LIMIT_EXCEEDED`: Plan usage limit reached
- ✅ `PROJECT_LIMIT_REACHED`: Maximum projects for plan
- ✅ `BLUEPRINT_ALREADY_USED`: Blueprint activation already used
- ✅ `CROSS_PROJECT_ACCESS_DENIED`: Tenant isolation violation
- ✅ `PROMPT_SCOPE_VIOLATION`: Forbidden data in prompt
- ✅ `AI_GENERATION_GLOBALLY_DISABLED`: Global kill switch active
- ✅ `AI_GENERATION_DISABLED_FOR_PROJECT`: Project kill switch active
- ✅ `AI_GENERATION_DISABLED_FOR_USER`: User kill switch active

### 🔄 Pending/To Be Implemented

#### 1. Stripe Webhook Integration
**Status**: Pending
**Requirements**:
- Subscription lifecycle webhook handlers
- Payment success/failure handling
- Plan upgrade/downgrade automation
- Grace period enforcement

**Suggested Implementation**:
- Create `app/core/billing.py` for Stripe integration
- Add webhook endpoint in `app/api/routes.py`
- Integrate with `ProjectEntitlement` model

#### 2. Abuse Detection & Incident Response
**Status**: Pending
**Requirements**:
- Excessive retry detection
- Prompt injection detection
- Cost anomaly detection
- Bulk spam detection
- Incident response handlers

**Suggested Implementation**:
- Create `app/core/abuse_detection.py`
- Add abuse detection triggers
- Integrate with audit logging
- Create incident response procedures

#### 3. FastAPI Middleware & Dependencies
**Status**: Partial
**Requirements**:
- RBAC middleware for route protection
- Entitlement middleware for feature gating
- Tenant isolation middleware for project scoping
- Audit logging middleware for automatic event logging

**Suggested Implementation**:
- Create `app/api/middleware/rbac.py`
- Create `app/api/middleware/entitlements.py`
- Create `app/api/middleware/tenant_isolation.py`
- Update route dependencies in `app/api/routes.py`

#### 4. Route Integration
**Status**: Pending
**Requirements**:
- Add RBAC checks to protected endpoints
- Add entitlement checks to feature endpoints
- Add tenant isolation to all project-scoped queries
- Add audit logging to all state-changing actions

**Files to Update**:
- `app/api/routes.py`: Add middleware and dependencies
- `app/api/routes/pages.py`: Integrate with security modules
- `app/api/routes/jobs.py`: Add entitlement checks
- All route files: Add project_id validation

## Usage Examples

### 1. Encrypt API Key (BYOK)

```python
from app.core.security import get_encryption_manager, APIKeyManager

encryption_manager = get_encryption_manager()
api_key_manager = APIKeyManager(encryption_manager)

# Encrypt API key for storage
encrypted_data = api_key_manager.encrypt_api_key(
    api_key="sk-...",
    project_id="project-uuid"
)

# Store encrypted_data in project_ai_settings table
# encrypted_data = {
#     "encrypted": "...",
#     "iv": "...",
#     "auth_tag": "..."
# }

# Decrypt for use (never display)
decrypted_key = api_key_manager.decrypt_api_key(
    encrypted_data=encrypted_data,
    project_id="project-uuid"
)
```

### 2. Check Entitlements

```python
from app.core.entitlements import require_feature, has_access
from app.exceptions import GovernanceError

# Check if project has access to feature
if has_access(project_id, "draft_generation", db):
    # Allow generation
    pass
else:
    # Block with error
    raise GovernanceError(...)

# Or use require_feature (raises if no access)
try:
    entitlements = require_feature(project_id, "draft_generation", db)
    # Proceed with generation
except GovernanceError as e:
    # Handle entitlement error
    pass
```

### 3. RBAC Permission Check

```python
from app.core.rbac import require_permission, Role

# Require permission for action
try:
    role = await require_permission(
        user_id=user_id,
        project_id=project_id,
        action="drafts.generate",
        db=db
    )
    # Permission granted, proceed
except HTTPException as e:
    # Permission denied
    pass
```

### 4. Audit Logging

```python
from app.core.audit import get_audit_logger

audit_logger = get_audit_logger(db)

# Log validation run
await audit_logger.log_validation_run(
    project_id=project_id,
    page_id=page_id,
    user_id=user_id,
    result=True,
    blocks=[],
    warnings=[],
    doctrine_sections=["Section 8"],
    actor_ip=request.client.host,
    actor_user_agent=request.headers.get("user-agent")
)

# Log generation attempt
await audit_logger.log_generation_attempt(
    project_id=project_id,
    job_id=job_id,
    page_id=page_id,
    user_id=user_id,
    provider="openai",
    model="gpt-4-turbo",
    tokens_estimated=5000
)
```

### 5. Kill Switch Check

```python
from app.core.kill_switch import get_kill_switch_manager

kill_switch = get_kill_switch_manager(db)

# Check if generation is allowed
try:
    await kill_switch.check_generation_allowed(
        project_id=project_id,
        user_id=user_id
    )
    # Generation allowed, proceed
except GovernanceError as e:
    # Generation disabled
    pass
```

### 6. Tenant Isolation Enforcement

```python
from app.core.tenant_isolation import enforce_project_isolation

# Enforce project isolation before querying
project = await enforce_project_isolation(
    project_id=project_id,
    user_organization_id=user.organization_id,
    db=db
)

# All queries MUST filter by project_id
pages = await db.execute(
    select(Page).where(Page.site_id == project.site_id)
)
```

## Environment Variables Required

Add to `.env`:

```bash
# Master encryption key for BYOK (32 bytes = 256 bits)
# Generate with: openssl rand -hex 32
SILOQ_MASTER_ENCRYPTION_KEY=your-32-byte-hex-key-here

# Global kill switch (default: true)
GLOBAL_GENERATION_ENABLED=true

# Stripe keys (for billing integration)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Migration Instructions

1. **Run Migration**:
   ```bash
   cd migrations
   psql -d siloq_db -f V012__security_entitlements_system.sql
   ```

2. **Verify Migration**:
   ```sql
   -- Check tables created
   \dt

   -- Verify system_events is immutable
   UPDATE system_events SET event_type = 'test' WHERE id = '...';
   -- Should raise error: "system_events table is immutable"
   ```

3. **Create Initial Organization & User**:
   ```python
   # Use CLI or API to create organization and user
   ```

## Testing Checklist

- [ ] Database migration runs successfully
- [ ] All models load without errors
- [ ] API key encryption/decryption works
- [ ] RBAC permissions enforce correctly
- [ ] Entitlement checks block/grant appropriately
- [ ] Audit logging creates immutable events
- [ ] Tenant isolation prevents cross-project access
- [ ] Kill switches work at all levels
- [ ] Error codes return correct HTTP status codes
- [ ] Prompt isolation validates forbidden patterns

## Next Steps

1. **Implement FastAPI Middleware**: Create middleware for automatic RBAC, entitlement, and tenant isolation checks
2. **Integrate Routes**: Update all route handlers to use new security modules
3. **Stripe Integration**: Implement billing webhooks and subscription management
4. **Abuse Detection**: Add automated abuse detection and incident response
5. **Testing**: Comprehensive integration tests for all security features
6. **Documentation**: API documentation with security requirements

## Notes

- All queries **MUST** filter by `project_id` for tenant isolation
- API keys are **NEVER** stored in plaintext - always encrypted
- Audit logs are **IMMUTABLE** - no updates or deletes allowed
- Kill switches work at **three levels**: global, project, user
- RBAC permissions are **enforced server-side** - UI only reflects
- Entitlements are **checked on every feature request** - no caching

## Security Considerations

1. **Encryption Keys**: Master encryption key must be stored securely (AWS KMS, Vault, etc.)
2. **Key Rotation**: Implement key rotation for master encryption key (90 days)
3. **Audit Log Retention**: Configure retention policy for system_events (90 days recommended)
4. **API Key Validation**: Test API keys before storing (validate with provider)
5. **Rate Limiting**: Integrate with existing rate limiting for abuse prevention
6. **MFA**: Support MFA for owner/admin roles (future enhancement)
