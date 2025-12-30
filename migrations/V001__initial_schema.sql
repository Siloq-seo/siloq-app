-- Siloq Core Database Schema v1.1
-- Initial schema with structural guarantees
-- Idempotent migration - safe to run multiple times

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Sites: Top-level website entities
CREATE TABLE IF NOT EXISTS sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_site_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_site_domain_not_empty CHECK (length(trim(domain)) > 0),
    CONSTRAINT uniq_site_domain UNIQUE (domain)
);

-- Pages: Core content pages with normalized path enforcement
CREATE TABLE IF NOT EXISTS pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    
    -- Path management with normalization
    path TEXT NOT NULL,
    normalized_path TEXT GENERATED ALWAYS AS (lower(trim(path))) STORED,
    
    -- Content
    title TEXT NOT NULL,
    body TEXT,
    
    -- Proposal flag (v1.3.1 patch)
    is_proposal BOOLEAN NOT NULL DEFAULT false,
    
    -- Status tracking
    status TEXT NOT NULL DEFAULT 'draft',
    
    -- Authority preservation
    authority_score FLOAT DEFAULT 0.0,
    source_urls JSONB DEFAULT '[]'::jsonb,
    
    -- Vector embedding for cannibalization detection
    embedding vector(1536),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    decommissioned_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT chk_page_path_not_empty CHECK (length(trim(path)) > 0),
    CONSTRAINT chk_page_title_not_empty CHECK (length(trim(title)) > 0),
    CONSTRAINT chk_page_status_valid CHECK (status IN ('draft', 'pending_review', 'approved', 'published', 'decommissioned', 'blocked')),
    CONSTRAINT chk_authority_score_range CHECK (authority_score >= 0.0 AND authority_score <= 1.0),
    -- CRITICAL: Unique normalized path per site (prevents duplicates)
    CONSTRAINT uniq_page_normalized_path_per_site UNIQUE (site_id, normalized_path)
);

-- Keywords: One-to-one mapping with pages (canonical uniqueness)
CREATE TABLE IF NOT EXISTS keywords (
    keyword TEXT PRIMARY KEY,
    page_id UUID NOT NULL UNIQUE REFERENCES pages(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_keyword_not_empty CHECK (length(trim(keyword)) > 0),
    CONSTRAINT chk_keyword_normalized CHECK (keyword = lower(trim(keyword)))
);

-- Silos: Reverse silo structure (3-7 per site)
CREATE TABLE IF NOT EXISTS silos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_silo_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_silo_slug_not_empty CHECK (length(trim(slug)) > 0),
    CONSTRAINT chk_silo_position_range CHECK (position >= 1 AND position <= 7),
    CONSTRAINT uniq_silo_position_per_site UNIQUE (site_id, position),
    CONSTRAINT uniq_silo_slug_per_site UNIQUE (site_id, slug)
);

-- Page-Silo relationships
CREATE TABLE IF NOT EXISTS page_silos (
    page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    silo_id UUID NOT NULL REFERENCES silos(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (page_id, silo_id)
);

-- ============================================================================
-- AUDIT & TRACKING TABLES
-- ============================================================================

-- System Events: Comprehensive audit logging (v1.3.1 patch)
CREATE TABLE IF NOT EXISTS system_events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_event_type_not_empty CHECK (length(trim(event_type)) > 0),
    CONSTRAINT chk_entity_type_not_empty CHECK (length(trim(entity_type)) > 0)
);

-- Cannibalization Checks: Similarity detection records
CREATE TABLE IF NOT EXISTS cannibalization_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    compared_with_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    similarity_score FLOAT NOT NULL,
    threshold_exceeded BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_similarity_score_range CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
    CONSTRAINT chk_no_self_comparison CHECK (page_id != compared_with_id)
);

-- Generation Jobs: AI content generation tracking
CREATE TABLE IF NOT EXISTS generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT chk_job_status_valid CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT chk_job_id_not_empty CHECK (length(trim(job_id)) > 0)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Pages indexes
CREATE INDEX IF NOT EXISTS idx_pages_site_id ON pages(site_id);
CREATE INDEX IF NOT EXISTS idx_pages_normalized_path ON pages(normalized_path);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_is_proposal ON pages(is_proposal);
CREATE INDEX IF NOT EXISTS idx_pages_created_at ON pages(created_at);

-- Vector similarity index (for cannibalization detection)
CREATE INDEX IF NOT EXISTS idx_pages_embedding ON pages USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Keywords indexes
CREATE INDEX IF NOT EXISTS idx_keywords_page_id ON keywords(page_id);

-- Silos indexes
CREATE INDEX IF NOT EXISTS idx_silos_site_id ON silos(site_id);
CREATE INDEX IF NOT EXISTS idx_silos_position ON silos(site_id, position);

-- System events indexes
CREATE INDEX IF NOT EXISTS idx_system_events_entity ON system_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_system_events_created_at ON system_events(created_at);
CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type);

-- Cannibalization checks indexes
CREATE INDEX IF NOT EXISTS idx_cannibalization_page_id ON cannibalization_checks(page_id);
CREATE INDEX IF NOT EXISTS idx_cannibalization_compared_with ON cannibalization_checks(compared_with_id);
CREATE INDEX IF NOT EXISTS idx_cannibalization_created_at ON cannibalization_checks(created_at);

-- Generation jobs indexes
CREATE INDEX IF NOT EXISTS idx_generation_jobs_page_id ON generation_jobs(page_id);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_job_id ON generation_jobs(job_id);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
DROP TRIGGER IF EXISTS trigger_pages_updated_at ON pages;
CREATE TRIGGER trigger_pages_updated_at
    BEFORE UPDATE ON pages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_sites_updated_at ON sites;
CREATE TRIGGER trigger_sites_updated_at
    BEFORE UPDATE ON sites
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_silos_updated_at ON silos;
CREATE TRIGGER trigger_silos_updated_at
    BEFORE UPDATE ON silos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to log system events
CREATE OR REPLACE FUNCTION log_system_event()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO system_events (event_type, entity_type, entity_id, payload)
    VALUES (
        TG_OP,  -- INSERT, UPDATE, DELETE
        TG_TABLE_NAME,
        COALESCE(NEW.id, OLD.id),
        jsonb_build_object(
            'old', to_jsonb(OLD),
            'new', to_jsonb(NEW)
        )
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Apply system event logging triggers
DROP TRIGGER IF EXISTS trigger_sites_system_events ON sites;
CREATE TRIGGER trigger_sites_system_events
    AFTER INSERT OR UPDATE OR DELETE ON sites
    FOR EACH ROW
    EXECUTE FUNCTION log_system_event();

DROP TRIGGER IF EXISTS trigger_pages_system_events ON pages;
CREATE TRIGGER trigger_pages_system_events
    AFTER INSERT OR UPDATE OR DELETE ON pages
    FOR EACH ROW
    EXECUTE FUNCTION log_system_event();

DROP TRIGGER IF EXISTS trigger_keywords_system_events ON keywords;
CREATE TRIGGER trigger_keywords_system_events
    AFTER INSERT OR UPDATE OR DELETE ON keywords
    FOR EACH ROW
    EXECUTE FUNCTION log_system_event();

DROP TRIGGER IF EXISTS trigger_silos_system_events ON silos;
CREATE TRIGGER trigger_silos_system_events
    AFTER INSERT OR UPDATE OR DELETE ON silos
    FOR EACH ROW
    EXECUTE FUNCTION log_system_event();

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE sites IS 'Top-level website entities';
COMMENT ON TABLE pages IS 'Core content pages with normalized path enforcement. Each page has a unique normalized path per site.';
COMMENT ON TABLE keywords IS 'Keywords with one-to-one mapping to pages. Each keyword maps to exactly one page.';
COMMENT ON TABLE silos IS 'Reverse silo structure (3-7 per site). Position must be unique per site.';
COMMENT ON TABLE page_silos IS 'Many-to-many relationship between pages and silos';
COMMENT ON TABLE system_events IS 'Comprehensive audit log for all schema changes (v1.3.1)';
COMMENT ON TABLE cannibalization_checks IS 'Records of similarity checks between pages';
COMMENT ON TABLE generation_jobs IS 'AI content generation job tracking';

COMMENT ON COLUMN pages.normalized_path IS 'Automatically generated lowercase, trimmed path. Enforced unique per site.';
COMMENT ON COLUMN pages.is_proposal IS 'Flag to distinguish proposed vs. active entries (v1.3.1)';
COMMENT ON COLUMN keywords.keyword IS 'Normalized keyword (lowercase, trimmed). Primary key ensures uniqueness.';
COMMENT ON COLUMN keywords.page_id IS 'One-to-one mapping: each keyword maps to exactly one page. UNIQUE constraint enforces this.';

