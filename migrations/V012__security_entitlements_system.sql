-- V012: Security, Privacy & Compliance + Entitlement & Plan Enforcement
-- Implements Section 7 (Security) and Section 8 (Entitlements)
-- Idempotent migration - safe to run multiple times

-- ============================================================================
-- USERS & ORGANIZATIONS (Tenant Hierarchy)
-- ============================================================================

-- Organizations: Top-level tenant boundary
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    CONSTRAINT chk_org_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_org_slug_not_empty CHECK (length(trim(slug)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_deleted_at ON organizations(deleted_at) WHERE deleted_at IS NULL;

-- Users: Authentication and authorization
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT, -- NULL for OAuth users
    name TEXT,
    
    -- Roles: owner, admin, editor, viewer (enforced at application level)
    role TEXT NOT NULL DEFAULT 'viewer',
    
    -- Security
    generation_enabled BOOLEAN NOT NULL DEFAULT true, -- Per-user kill switch
    mfa_enabled BOOLEAN NOT NULL DEFAULT false,
    mfa_secret TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    
    CONSTRAINT chk_user_email_not_empty CHECK (length(trim(email)) > 0),
    CONSTRAINT chk_user_role_valid CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
    CONSTRAINT chk_user_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_organization_id ON users(organization_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Projects: Tenant isolation boundary (maps to Sites)
-- For backward compatibility, we'll link projects to sites
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE UNIQUE, -- 1:1 with sites
    
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    
    -- Soft delete
    deleted_at TIMESTAMPTZ,
    deletion_reason TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_project_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_project_slug_not_empty CHECK (length(trim(slug)) > 0),
    CONSTRAINT uniq_project_slug_per_org UNIQUE (organization_id, slug) WHERE deleted_at IS NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_organization_id ON projects(organization_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_projects_site_id ON projects(site_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(organization_id, slug) WHERE deleted_at IS NULL;

-- ============================================================================
-- ENTITLEMENTS & PLANS
-- ============================================================================

-- Plan types enum
DO $$ BEGIN
    CREATE TYPE plan_type_enum AS ENUM ('trial', 'blueprint', 'operator', 'agency', 'empire');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Project Entitlements: Plan and feature access
CREATE TABLE IF NOT EXISTS project_entitlements (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Plan
    plan_key plan_type_enum NOT NULL DEFAULT 'trial',
    subscription_status TEXT DEFAULT 'active', -- active, canceled, past_due, trialing
    subscription_id TEXT, -- Stripe subscription ID
    stripe_customer_id TEXT, -- Stripe customer ID (encrypted in application layer)
    
    -- Trial
    trial_ends_at TIMESTAMPTZ,
    trial_started_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Blueprint (one-time unlock)
    blueprint_activation_purchased BOOLEAN NOT NULL DEFAULT false,
    blueprint_activated_at TIMESTAMPTZ,
    blueprint_target_page_id UUID REFERENCES pages(id) ON DELETE SET NULL,
    
    -- Usage limits (soft limits, can be adjusted)
    max_concurrent_jobs INTEGER DEFAULT 5,
    max_drafts_per_day INTEGER DEFAULT 50,
    max_drafts_per_month INTEGER,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_subscription_status_valid CHECK (
        subscription_status IN ('active', 'canceled', 'past_due', 'trialing', 'incomplete', 'incomplete_expired')
    )
);

CREATE INDEX IF NOT EXISTS idx_project_entitlements_plan_key ON project_entitlements(plan_key);
CREATE INDEX IF NOT EXISTS idx_project_entitlements_subscription_id ON project_entitlements(subscription_id) WHERE subscription_id IS NOT NULL;

-- ============================================================================
-- API KEY SECURITY (BYOK - Bring Your Own Key)
-- ============================================================================

-- Project AI Settings: Encrypted API keys and generation settings
CREATE TABLE IF NOT EXISTS project_ai_settings (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    
    -- BYOK: Encrypted API keys (AES-256-GCM)
    api_key_encrypted BYTEA, -- Encrypted API key
    api_key_iv BYTEA, -- Initialization vector
    api_key_auth_tag BYTEA, -- Authentication tag for GCM
    
    -- Provider settings
    ai_provider TEXT DEFAULT 'openai', -- openai, anthropic, google
    ai_model TEXT DEFAULT 'gpt-4-turbo-preview',
    
    -- Generation controls
    generation_enabled BOOLEAN NOT NULL DEFAULT true, -- Per-project kill switch
    max_retries INTEGER DEFAULT 3,
    max_cost_per_job_usd FLOAT DEFAULT 10.0,
    
    -- API key validation tracking
    api_key_last_validated_at TIMESTAMPTZ,
    api_key_validation_failures INTEGER DEFAULT 0,
    api_key_last_failure_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_ai_provider_valid CHECK (ai_provider IN ('openai', 'anthropic', 'google')),
    CONSTRAINT chk_max_retries_positive CHECK (max_retries > 0),
    CONSTRAINT chk_max_cost_non_negative CHECK (max_cost_per_job_usd >= 0.0)
);

-- ============================================================================
-- ENHANCED AUDIT LOGGING (Immutable System Events)
-- ============================================================================

-- Drop and recreate system_events with enhanced schema
-- Note: We'll preserve existing data by creating new table first
CREATE TABLE IF NOT EXISTS system_events_new (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Actor
    actor_id UUID, -- user or null for system
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'system', 'agent')),
    actor_ip INET,
    actor_user_agent TEXT,
    
    -- Event
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARN', 'BLOCK', 'CRITICAL')),
    action TEXT NOT NULL,
    
    -- Target
    target_entity_type TEXT,
    target_entity_id UUID,
    
    -- Details
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_hash TEXT NOT NULL, -- SHA-256 hash of payload for integrity
    doctrine_section TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Migrate existing data if system_events exists (preserve old data)
DO $$
BEGIN
    -- Check if old system_events table exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'system_events' AND table_schema = 'public') THEN
        -- Migrate data to new structure
        INSERT INTO system_events_new (
            project_id, actor_id, actor_type, actor_ip, actor_user_agent,
            event_type, severity, action, target_entity_type, target_entity_id,
            payload, payload_hash, doctrine_section, created_at
        )
        SELECT 
            NULL, -- No project_id in old schema
            NULL, -- No actor_id in old schema
            'system', -- Default actor_type
            NULL, -- No IP in old schema
            NULL, -- No user agent in old schema
            event_type,
            CASE 
                WHEN event_type LIKE '%error%' OR event_type LIKE '%fail%' THEN 'WARN'
                ELSE 'INFO'
            END, -- Infer severity
            event_type, -- Use event_type as action
            entity_type,
            entity_id,
            payload,
            encode(digest(COALESCE(payload::text, '{}'), 'sha256'), 'hex'), -- Generate hash
            NULL, -- No doctrine_section in old schema
            created_at
        FROM system_events
        ON CONFLICT DO NOTHING; -- Prevent duplicates if run multiple times
        
        -- Rename old table for backup (after migration)
        ALTER TABLE IF EXISTS system_events RENAME TO system_events_old_backup;
    END IF;
END $$;

-- Replace old table with new one
DO $$
BEGIN
    -- Rename old table for backup if it exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'system_events' AND table_schema = 'public') THEN
        ALTER TABLE system_events RENAME TO system_events_old_backup;
    END IF;
    
    -- Rename new table to final name
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'system_events_new' AND table_schema = 'public') THEN
        ALTER TABLE system_events_new RENAME TO system_events;
    END IF;
END $$;

-- Create indexes after table rename
CREATE INDEX IF NOT EXISTS ix_system_events_project_time 
    ON system_events(project_id, created_at DESC) WHERE project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_system_events_type 
    ON system_events(event_type);
CREATE INDEX IF NOT EXISTS ix_system_events_severity 
    ON system_events(severity) WHERE severity IN ('BLOCK', 'CRITICAL');
CREATE INDEX IF NOT EXISTS ix_system_events_actor 
    ON system_events(actor_id, created_at DESC) WHERE actor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_system_events_target 
    ON system_events(target_entity_type, target_entity_id) WHERE target_entity_id IS NOT NULL;

-- Function to prevent updates/deletes (immutability)
CREATE OR REPLACE FUNCTION raise_immutable_violation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'system_events table is immutable - updates and deletes are not allowed';
END;
$$ LANGUAGE plpgsql;

-- Trigger to enforce immutability
DROP TRIGGER IF EXISTS prevent_system_events_modification ON system_events;
CREATE TRIGGER prevent_system_events_modification
    BEFORE UPDATE OR DELETE ON system_events
    FOR EACH ROW
    EXECUTE FUNCTION raise_immutable_violation();

-- ============================================================================
-- USAGE TRACKING (For plan limits)
-- ============================================================================

-- AI Usage Logs: Track token usage and costs
CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    generation_job_id UUID REFERENCES generation_jobs(id) ON DELETE SET NULL,
    
    -- Usage metrics
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd FLOAT DEFAULT 0.0,
    
    -- Request metadata
    prompt_length INTEGER,
    response_length INTEGER,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_tokens_non_negative CHECK (
        input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0
    ),
    CONSTRAINT chk_cost_non_negative CHECK (cost_usd >= 0.0)
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_project_time 
    ON ai_usage_logs(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_job_id 
    ON ai_usage_logs(generation_job_id) WHERE generation_job_id IS NOT NULL;

-- Monthly Usage Summary: Aggregated usage per project per month
CREATE TABLE IF NOT EXISTS monthly_usage_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    
    -- Aggregated metrics
    total_drafts_generated INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd FLOAT DEFAULT 0.0,
    total_jobs INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uniq_monthly_usage_per_project UNIQUE (project_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_usage_project 
    ON monthly_usage_summary(project_id, year DESC, month DESC);

-- ============================================================================
-- COMMENTS (Documentation)
-- ============================================================================

COMMENT ON TABLE organizations IS 'Top-level tenant boundary. Users belong to organizations.';
COMMENT ON TABLE users IS 'User accounts with authentication and RBAC roles (owner, admin, editor, viewer).';
COMMENT ON TABLE projects IS 'Tenant isolation boundary. Each project maps 1:1 to a site. All queries MUST filter by project_id.';
COMMENT ON TABLE project_entitlements IS 'Plan entitlements and feature access per project. Plans: trial, blueprint, operator, agency, empire.';
COMMENT ON TABLE project_ai_settings IS 'BYOK (Bring Your Own Key) settings with AES-256-GCM encrypted API keys.';
COMMENT ON TABLE system_events IS 'Immutable audit log for all actions. All privileged actions must be logged here.';
COMMENT ON TABLE ai_usage_logs IS 'Track AI token usage and costs per generation job for billing and rate limiting.';
COMMENT ON TABLE monthly_usage_summary IS 'Aggregated monthly usage per project for plan limit enforcement.';

COMMENT ON COLUMN users.generation_enabled IS 'Per-user kill switch for AI generation.';
COMMENT ON COLUMN project_ai_settings.api_key_encrypted IS 'AES-256-GCM encrypted API key. Never store plaintext.';
COMMENT ON COLUMN project_ai_settings.generation_enabled IS 'Per-project kill switch for AI generation.';
COMMENT ON COLUMN system_events.payload_hash IS 'SHA-256 hash of payload JSON for integrity verification.';
COMMENT ON COLUMN project_entitlements.blueprint_target_page_id IS 'Blueprint activation allows one target page only.';
