-- Week 6: Lifecycle Gates - Publish & Lifecycle Management
-- Adds redirect tracking and ensures silo decay is properly logged

-- ============================================================================
-- REDIRECT TRACKING
-- ============================================================================
-- Note: Redirects are stored in pages.governance_checks JSONB column
-- This migration ensures the column exists and has proper indexing

-- Ensure governance_checks column exists (should already exist from V009)
ALTER TABLE pages
ADD COLUMN IF NOT EXISTS governance_checks JSONB DEFAULT '{}'::jsonb;

-- Ensure GIN index exists for governance_checks queries
CREATE INDEX IF NOT EXISTS idx_pages_governance_checks 
ON pages USING GIN (governance_checks);

-- ============================================================================
-- ENHANCE SILO_DECAY LOGGING
-- ============================================================================
-- Ensure silo decay events are properly logged with all details

-- Update trigger_silo_decay function to ensure comprehensive logging
CREATE OR REPLACE FUNCTION trigger_silo_decay()
RETURNS TRIGGER AS $$
DECLARE
    decay_threshold INTERVAL := INTERVAL '90 days';
    archived_count INTEGER := 0;
    event_payload JSONB;
BEGIN
    -- Archive stale proposals (older than threshold)
    IF NEW.is_proposal = true THEN
        UPDATE pages
        SET 
            status = 'decommissioned',
            decommissioned_at = NOW(),
            is_proposal = false
        WHERE 
            id = NEW.id
            AND is_proposal = true
            AND created_at < NOW() - decay_threshold
            AND status NOT IN ('published', 'decommissioned');
        
        GET DIAGNOSTICS archived_count = ROW_COUNT;
        
        IF archived_count > 0 THEN
            -- Enhanced logging with page details
            event_payload := jsonb_build_object(
                'reason', 'stale_proposal',
                'threshold_days', 90,
                'created_at', NEW.created_at,
                'page_id', NEW.id,
                'page_title', NEW.title,
                'page_path', NEW.path,
                'site_id', NEW.site_id
            );
            
            INSERT INTO system_events (event_type, entity_type, entity_id, payload)
            VALUES (
                'SILO_DECAY',
                'pages',
                NEW.id,
                event_payload
            );
        END IF;
    END IF;
    
    -- Archive orphaned pages (no keyword, no silo, older than threshold)
    UPDATE pages p
    SET 
        status = 'decommissioned',
        decommissioned_at = NOW()
    WHERE 
        p.id NOT IN (SELECT page_id FROM keywords WHERE page_id IS NOT NULL)
        AND p.id NOT IN (SELECT page_id FROM page_silos WHERE page_id IS NOT NULL)
        AND p.status = 'draft'
        AND p.created_at < NOW() - decay_threshold
        AND p.status != 'decommissioned';
    
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    
    IF archived_count > 0 THEN
        -- Enhanced batch logging
        event_payload := jsonb_build_object(
            'reason', 'orphaned_pages',
            'archived_count', archived_count,
            'threshold_days', 90,
            'timestamp', NOW()
        );
        
        INSERT INTO system_events (event_type, entity_type, entity_id, payload)
        VALUES (
            'SILO_DECAY',
            'pages',
            NULL,
            event_payload
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN pages.governance_checks IS 'Week 6: Stores governance checks, decommission data, and redirect information';
COMMENT ON FUNCTION trigger_silo_decay() IS 'Week 6: Enhanced silo decay with comprehensive logging';

