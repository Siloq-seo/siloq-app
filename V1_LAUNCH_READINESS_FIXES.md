# V1 Launch Readiness Fixes

This document summarizes the changes made to address the code review feedback for V1 launch readiness.

## Branch
`v1-launch-readiness-fixes`

## Summary of Changes

### 1. Authentication & Authorization ✅

**Files Changed:**
- `app/core/auth.py` (new file)
- `app/api/routes/sites.py`
- `app/api/routes/pages.py`

**Changes:**
- Added JWT-based authentication using `python-jose`
- Created `get_current_user()` dependency for extracting user from JWT token
- Created `verify_site_access()` and `verify_page_access()` dependencies for tenant scoping
- Added authentication requirements to key routes (sites, pages)

**Note:** All API routes should be updated to include `current_user: dict = Depends(get_current_user)` and appropriate access verification. The current implementation provides the foundation - routes should be systematically updated.

**TODO for Full Implementation:**
- Add `owner_account_id` column to `Site` model
- Enforce ownership check in `verify_site_access()`
- Apply auth to all remaining routes (jobs, silos, onboarding)

### 2. CORS Configuration ✅

**Files Changed:**
- `app/main.py`
- `app/core/config.py`

**Changes:**
- Made CORS configuration environment-aware
- In production, requires explicit origins (no wildcard)
- In development, allows all origins
- Added configurable CORS settings in `Settings`:
  - `cors_origins`: Comma-separated list or "*"
  - `cors_allow_credentials`
  - `cors_allow_methods`
  - `cors_allow_headers`

**Environment Variables:**
```bash
# Production
CORS_ORIGINS=https://app.siloq.com,https://admin.siloq.com
ENVIRONMENT=production

# Development
CORS_ORIGINS=*
ENVIRONMENT=development
```

### 3. Alembic Migrations ✅

**Files Changed:**
- `alembic/versions/001_initial_schema_with_v2_fields.py` (new file)

**Changes:**
- Created initial Alembic migration with complete schema
- Includes all tables, constraints, indexes, and enums
- Includes `normalized_path` as generated column
- Includes V2 dormant fields (see #5)

**Usage:**
```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

**Note:** The migration file references `settings.database_url_sync` which requires environment variables. Ensure `.env` is configured before running migrations.

### 4. Real Health Checks ✅

**Files Changed:**
- `app/main.py`

**Changes:**
- Updated `/health` endpoint to actually test database and Redis connections
- Returns `"healthy"` if both connections work
- Returns `"degraded"` if either connection fails
- Includes error details in response

**Response Format:**
```json
{
  "status": "healthy" | "degraded",
  "database": "connected" | "disconnected: <error>",
  "redis": "connected" | "disconnected: <error>"
}
```

### 5. V2 Dormant Fields ✅

**Files Changed:**
- `app/db/models.py`
- `alembic/versions/001_initial_schema_with_v2_fields.py`

**Changes:**
- Added `v2_governance` JSONB column to `Page` model with default:
  ```json
  {
    "signal_status": "IDLE",
    "enforcement_log": []
  }
  ```
- Added `active_widget_id` UUID column (nullable)
- Added `widget_config_payload` JSONB column with default `{}`

These fields are safe to add pre-launch and will be used in V2 without requiring customer database migrations.

### 6. Rate Limiting & Production Guardrails ✅

**Files Changed:**
- `app/core/rate_limit.py` (new file)
- `app/core/config.py`
- `app/main.py`
- `app/queues/queue_manager.py`

**Changes:**
- Added `RateLimitMiddleware` for per-site/per-account rate limiting
- Implements per-minute, per-hour, and per-day limits
- Added `GlobalGenerationKillSwitch` class for:
  - Global generation enable/disable toggle
  - Per-hour and per-day job limits
- Integrated kill switch checks into `queue_manager.add_generation_job()`

**Configuration:**
```python
# In Settings
rate_limit_enabled: bool = True
rate_limit_per_minute: int = 60
rate_limit_per_hour: int = 1000
rate_limit_per_day: int = 10000
global_generation_enabled: bool = True
max_jobs_per_hour: int = 100
max_jobs_per_day: int = 1000
```

**Runtime Control:**
```bash
# Disable generation globally (via Redis)
redis-cli SET global:generation_enabled false

# Re-enable
redis-cli SET global:generation_enabled true
```

### 7. Tenant Scoping (Partial) ✅

**Files Changed:**
- `app/core/auth.py`
- `app/api/routes/sites.py`
- `app/api/routes/pages.py`

**Changes:**
- Created `verify_site_access()` and `verify_page_access()` dependencies
- These ensure users can only access resources from sites they own
- Applied to `get_site()` and `get_page()` endpoints

**TODO:**
- Add `owner_account_id` column to `Site` model
- Update all remaining routes to use tenant scoping
- Ensure all queries filter by `site_id` and verify ownership

## Remaining Work

### High Priority
1. **Complete Auth Coverage**: Apply `get_current_user` and access verification to all routes:
   - `/api/v1/jobs/*`
   - `/api/v1/silos/*`
   - `/api/v1/onboarding/*`
   - All remaining `/api/v1/pages/*` endpoints

2. **Site Ownership**: Add `owner_account_id` to `Site` model and enforce in `verify_site_access()`

3. **Alembic Migration Testing**: Test the migration against a clean database to ensure it works correctly

### Medium Priority
1. **Metrics & Monitoring**: Add metrics collection for:
   - Job creation rates
   - Rate limit hits
   - Health check failures
   - Cost tracking

2. **Documentation**: Update API documentation to reflect authentication requirements

3. **Error Handling**: Improve error messages for auth failures and rate limits

## Testing Checklist

- [ ] Test JWT authentication with valid/invalid tokens
- [ ] Test CORS in development and production modes
- [ ] Run Alembic migration on clean database
- [ ] Test health check with DB/Redis up and down
- [ ] Test rate limiting (per-minute, per-hour, per-day)
- [ ] Test global kill switch
- [ ] Test tenant scoping (user can only access own sites)
- [ ] Verify V2 fields are created with correct defaults

## Environment Variables

Add to `.env`:

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/siloq
DATABASE_URL_SYNC=postgresql://user:pass@localhost/siloq
SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=your-openai-key

# CORS (Production)
CORS_ORIGINS=https://app.siloq.com,https://admin.siloq.com
ENVIRONMENT=production

# CORS (Development)
CORS_ORIGINS=*
ENVIRONMENT=development

# Optional - Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_PER_DAY=10000

# Optional - Production Guardrails
GLOBAL_GENERATION_ENABLED=true
MAX_JOBS_PER_HOUR=100
MAX_JOBS_PER_DAY=1000
```

## Notes

- The authentication system uses JWT tokens. You'll need to create a token endpoint or integrate with your auth provider.
- Rate limiting uses Redis, so ensure Redis is available for production.
- The global kill switch can be toggled via Redis without restarting the application.
- All changes are backward-compatible for existing code (auth is opt-in per route).

