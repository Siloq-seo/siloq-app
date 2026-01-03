-- Siloq Core Database Schema v1.3.1
-- SILO_DECAY trigger implementation
-- Idempotent migration - safe to run multiple times

-- ============================================================================
-- SILO_DECAY TRIGGER
-- ============================================================================
-- Automated cleanup/archival mechanism for stale data
-- Archives or deletes entries based on decay rules

CREATE OR REPLACE FUNCTION trigger_silo_decay()
RETURNS TRIGGER AS $$
DECLARE
    decay_threshold INTERVAL := INTERVAL '90 days';  -- Configurable threshold
    archived_count INTEGER := 0;
BEGIN
    -- Archive stale proposals (older than threshold)
    -- Correction Sprint: Exclude product pages from decay
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
            AND status NOT IN ('published', 'decommissioned')
            -- Task 3: Product Protection - Exclude product pages from decay
            AND (governance_checks->>'page_type' IS NULL OR governance_checks->>'page_type' != 'product');
        
        GET DIAGNOSTICS archived_count = ROW_COUNT;
        
        IF archived_count > 0 THEN
            -- Log decay event
            INSERT INTO system_events (event_type, entity_type, entity_id, payload)
            VALUES (
                'SILO_DECAY',
                'pages',
                NEW.id,
                jsonb_build_object(
                    'reason', 'stale_proposal',
                    'threshold_days', 90,
                    'created_at', NEW.created_at
                )
            );
        END IF;
    END IF;
    
    -- Archive orphaned pages (no keyword, no silo, older than threshold)
    -- Correction Sprint: Exclude product pages from decay
    UPDATE pages p
    SET 
        status = 'decommissioned',
        decommissioned_at = NOW()
    WHERE 
        p.id NOT IN (SELECT page_id FROM keywords WHERE page_id IS NOT NULL)
        AND p.id NOT IN (SELECT page_id FROM page_silos WHERE page_id IS NOT NULL)
        AND p.status = 'draft'
        AND p.created_at < NOW() - decay_threshold
        AND p.status != 'decommissioned'
        -- Task 3: Product Protection - Exclude product pages from decay
        AND (p.governance_checks->>'page_type' IS NULL OR p.governance_checks->>'page_type' != 'product');
    
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    
    IF archived_count > 0 THEN
        -- Log batch decay event
        INSERT INTO system_events (event_type, entity_type, entity_id, payload)
        VALUES (
            'SILO_DECAY',
            'pages',
            NULL,
            jsonb_build_object(
                'reason', 'orphaned_pages',
                'archived_count', archived_count,
                'threshold_days', 90
            )
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply SILO_DECAY trigger on pages table
-- Runs on INSERT and UPDATE to catch stale data
DROP TRIGGER IF EXISTS trigger_pages_silo_decay ON pages;
CREATE TRIGGER trigger_pages_silo_decay
    AFTER INSERT OR UPDATE ON pages
    FOR EACH ROW
    WHEN (NEW.is_proposal = true OR NEW.status = 'draft')
    EXECUTE FUNCTION trigger_silo_decay();

-- ============================================================================
-- HELPER FUNCTION: Manual decay execution
-- ============================================================================
-- Allows manual execution of decay logic for maintenance

CREATE OR REPLACE FUNCTION execute_silo_decay(threshold_days INTEGER DEFAULT 90)
RETURNS TABLE (
    archived_count INTEGER,
    event_id BIGINT
) AS $$
DECLARE
    archived INTEGER := 0;
    event_id_val BIGINT;
BEGIN
    -- Archive stale proposals
    -- Correction Sprint: Exclude product pages from decay
    UPDATE pages
    SET 
        status = 'decommissioned',
        decommissioned_at = NOW(),
        is_proposal = false
    WHERE 
        is_proposal = true
        AND created_at < NOW() - (threshold_days || ' days')::INTERVAL
        AND status NOT IN ('published', 'decommissioned')
        -- Task 3: Product Protection - Exclude product pages from decay
        AND (governance_checks->>'page_type' IS NULL OR governance_checks->>'page_type' != 'product');
    
    GET DIAGNOSTICS archived = ROW_COUNT;
    
    -- Archive orphaned pages
    -- Correction Sprint: Exclude product pages from decay
    UPDATE pages p
    SET 
        status = 'decommissioned',
        decommissioned_at = NOW()
    WHERE 
        p.id NOT IN (SELECT page_id FROM keywords WHERE page_id IS NOT NULL)
        AND p.id NOT IN (SELECT page_id FROM page_silos WHERE page_id IS NOT NULL)
        AND p.status = 'draft'
        AND p.created_at < NOW() - (threshold_days || ' days')::INTERVAL
        AND p.status != 'decommissioned'
        -- Task 3: Product Protection - Exclude product pages from decay
        AND (p.governance_checks->>'page_type' IS NULL OR p.governance_checks->>'page_type' != 'product');
    
    GET DIAGNOSTICS archived = archived + ROW_COUNT;
    
    -- Log manual decay event
    INSERT INTO system_events (event_type, entity_type, entity_id, payload)
    VALUES (
        'SILO_DECAY_MANUAL',
        'pages',
        NULL,
        jsonb_build_object(
            'threshold_days', threshold_days,
            'archived_count', archived
        )
    )
    RETURNING id INTO event_id_val;
    
    RETURN QUERY SELECT archived, event_id_val;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trigger_silo_decay() IS 'Automated cleanup/archival mechanism for stale data (v1.3.1)';
COMMENT ON FUNCTION execute_silo_decay(INTEGER) IS 'Manual execution of decay logic for maintenance';

