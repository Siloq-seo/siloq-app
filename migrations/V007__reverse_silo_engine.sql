-- Siloq Week 4: Reverse Silo Engine
-- Authority funnels, entity inheritance, anchor governance
-- Idempotent migration - safe to run multiple times

-- ============================================================================
-- CLUSTERS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_cluster_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT uniq_cluster_name_per_site UNIQUE (site_id, name)
);

-- ============================================================================
-- CLUSTER-PAGE RELATIONSHIPS
-- ============================================================================

CREATE TABLE IF NOT EXISTS cluster_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
    page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member', -- 'member', 'anchor', 'hub'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_cluster_page_role_valid CHECK (role IN ('member', 'anchor', 'hub')),
    CONSTRAINT uniq_cluster_page UNIQUE (cluster_id, page_id)
);

-- ============================================================================
-- SILO ENHANCEMENTS
-- ============================================================================

-- Add columns to silos table for finalization and entity inheritance
ALTER TABLE silos
    ADD COLUMN IF NOT EXISTS is_finalized BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS entity_type TEXT, -- e.g., 'topic', 'category', 'service'
    ADD COLUMN IF NOT EXISTS parent_silo_id UUID REFERENCES silos(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS authority_funnel_score FLOAT DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS anchor_governance_enabled BOOLEAN NOT NULL DEFAULT TRUE;

-- ============================================================================
-- SUPPORTING PAGES TRACKING
-- ============================================================================

-- Add supporting page relationship to page_silos
-- Note: page_silos uses composite primary key (page_id, silo_id)
ALTER TABLE page_silos
    ADD COLUMN IF NOT EXISTS is_supporting_page BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS supporting_role TEXT, -- 'pillar', 'cluster', 'topic'
    ADD COLUMN IF NOT EXISTS authority_weight FLOAT DEFAULT 1.0;

-- Add constraint for authority weight
ALTER TABLE page_silos
    ADD CONSTRAINT chk_authority_weight_range CHECK (authority_weight >= 0.0 AND authority_weight <= 2.0);

-- ============================================================================
-- ANCHOR GOVERNANCE
-- ============================================================================

CREATE TABLE IF NOT EXISTS anchor_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    to_page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    anchor_text TEXT NOT NULL,
    silo_id UUID REFERENCES silos(id) ON DELETE SET NULL,
    is_internal BOOLEAN NOT NULL DEFAULT TRUE,
    authority_passed FLOAT DEFAULT 0.0, -- Calculated authority passed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_anchor_text_not_empty CHECK (length(trim(anchor_text)) > 0),
    CONSTRAINT chk_no_self_link CHECK (from_page_id != to_page_id),
    CONSTRAINT chk_authority_passed_range CHECK (authority_passed >= 0.0 AND authority_passed <= 1.0),
    CONSTRAINT uniq_anchor_link UNIQUE (from_page_id, to_page_id, anchor_text)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_clusters_site_id ON clusters(site_id);
CREATE INDEX IF NOT EXISTS idx_cluster_pages_cluster_id ON cluster_pages(cluster_id);
CREATE INDEX IF NOT EXISTS idx_cluster_pages_page_id ON cluster_pages(page_id);
CREATE INDEX IF NOT EXISTS idx_silos_is_finalized ON silos(is_finalized);
CREATE INDEX IF NOT EXISTS idx_silos_parent_silo_id ON silos(parent_silo_id);
CREATE INDEX IF NOT EXISTS idx_page_silos_is_supporting ON page_silos(is_supporting_page);
CREATE INDEX IF NOT EXISTS idx_anchor_links_from_page ON anchor_links(from_page_id);
CREATE INDEX IF NOT EXISTS idx_anchor_links_to_page ON anchor_links(to_page_id);
CREATE INDEX IF NOT EXISTS idx_anchor_links_silo_id ON anchor_links(silo_id);

-- ============================================================================
-- FUNCTIONS FOR AUTHORITY FUNNEL
-- ============================================================================

-- Function to prevent sideways authority leakage
CREATE OR REPLACE FUNCTION prevent_sideways_authority_leakage()
RETURNS TRIGGER AS $$
DECLARE
    from_silo_id UUID;
    to_silo_id UUID;
BEGIN
    -- Get silos for from_page and to_page
    SELECT ps1.silo_id INTO from_silo_id
    FROM page_silos ps1
    WHERE ps1.page_id = NEW.from_page_id
    LIMIT 1;
    
    SELECT ps2.silo_id INTO to_silo_id
    FROM page_silos ps2
    WHERE ps2.page_id = NEW.to_page_id
    LIMIT 1;
    
    -- If both pages are in different silos (sideways), block if governance enabled
    IF from_silo_id IS NOT NULL AND to_silo_id IS NOT NULL 
       AND from_silo_id != to_silo_id THEN
        -- Check if anchor governance is enabled for either silo
        IF EXISTS (
            SELECT 1 FROM silos 
            WHERE id IN (from_silo_id, to_silo_id) 
            AND anchor_governance_enabled = TRUE
        ) THEN
            RAISE EXCEPTION 'Sideways authority leakage blocked: Cannot link from silo % to silo %. Anchor governance enabled.',
                from_silo_id, to_silo_id;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply sideways leakage prevention
DROP TRIGGER IF EXISTS trigger_prevent_sideways_leakage ON anchor_links;
CREATE TRIGGER trigger_prevent_sideways_leakage
    BEFORE INSERT OR UPDATE ON anchor_links
    FOR EACH ROW
    EXECUTE FUNCTION prevent_sideways_authority_leakage();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE clusters IS 'Content clusters for grouping related pages';
COMMENT ON TABLE cluster_pages IS 'Many-to-many relationship between clusters and pages';
COMMENT ON COLUMN silos.is_finalized IS 'Whether silo structure is finalized (no more changes allowed)';
COMMENT ON COLUMN silos.entity_type IS 'Type of entity this silo represents (topic, category, service, etc.)';
COMMENT ON COLUMN silos.parent_silo_id IS 'Parent silo for hierarchical structure';
COMMENT ON COLUMN silos.authority_funnel_score IS 'Calculated authority funnel score for this silo';
COMMENT ON COLUMN page_silos.is_supporting_page IS 'Whether this page supports the silo (not a main page)';
COMMENT ON TABLE anchor_links IS 'Governed anchor links with authority tracking';
COMMENT ON COLUMN anchor_links.authority_passed IS 'Calculated authority passed through this link';

