-- V013: API Keys Table for WordPress Plugin Integration
-- Description: Create api_keys table to support API key authentication for WordPress plugin

-- Create api_keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash
    key_prefix VARCHAR(10) NOT NULL,       -- First 8 chars for identification
    name VARCHAR NOT NULL,                  -- Descriptive name

    -- Permissions
    scopes JSONB NOT NULL DEFAULT '["read", "write"]'::jsonb,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_reason TEXT,

    -- Usage tracking
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT chk_api_key_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_key_hash_length CHECK (length(trim(key_hash)) = 64),
    CONSTRAINT chk_key_prefix_length CHECK (length(trim(key_prefix)) >= 8),
    CONSTRAINT chk_usage_count_non_negative CHECK (usage_count >= 0)
);

-- Create indexes
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_site_id ON api_keys(site_id);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);

-- Add comment
COMMENT ON TABLE api_keys IS 'API keys for WordPress plugin and external integrations with scope-based permissions';
COMMENT ON COLUMN api_keys.key_hash IS 'SHA-256 hash of the API key for secure storage';
COMMENT ON COLUMN api_keys.key_prefix IS 'First 8 characters for key identification without exposing full key';
COMMENT ON COLUMN api_keys.scopes IS 'JSON array of allowed scopes: read, write, admin';
