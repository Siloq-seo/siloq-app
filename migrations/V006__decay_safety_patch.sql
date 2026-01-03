-- V1 Stress Test: Decay Safety Patch
-- Prevents decay logic from archiving Product and Service_Core pages
-- Idempotent migration - safe to run multiple times

-- ============================================================================
-- UPDATED SILO_DECAY TRIGGER
-- ============================================================================
-- Updated to exclude Product and Service_Core pages from decay

CREATE OR REPLACE FUNCTION trigger_silo_decay()
RETURNS TRIGGER AS $$
DECLARE
    decay_threshold INTERVAL := INTERVAL '90 days';  -- Configurable threshold
    archived_count INTEGER := 0;
    page_type_val TEXT;
BEGIN
    -- Get page type from governance_checks metadata
    page_type_val := NEW.governance_checks->>'page_type';
    
    -- Skip decay for Product and Service_Core pages (V1 Stress Test Patch)
    IF page_type_val IN ('Product', 'Service_Core', 'product', 'service_core') THEN
        RETURN NEW;  -- Skip decay for these page types
    END IF;
    
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
            -- Log decay event
            INSERT INTO system_events (event_type, entity_type, entity_id, payload)
            VALUES (
                'SILO_DECAY',
                'pages',
                NEW.id,
                jsonb_build_object(
                    'reason', 'stale_proposal',
                    'threshold_days', 90,
                    'created_at', NEW.created_at,
                    'page_type', page_type_val
                )
            );
        END IF;
    END IF;
    
    -- Archive orphaned pages (no keyword, no silo, older than threshold)
    -- EXCLUDE Product and Service_Core pages
    UPDATE pages p
    SET 
        status = 'decommissioned',
        decommissioned_at = NOW()
    WHERE 
        p.id NOT IN (SELECT page_id FROM keywords WHERE page_id IS NOT NULL)
        AND p.id NOT IN (SELECT page_id FROM page_silos WHERE page_id IS NOT NULL)
        AND (p.governance_checks->>'page_type') NOT IN ('Product', 'Service_Core', 'product', 'service_core')
        AND p.status = 'draft'
        AND p.created_at < NOW() - decay_threshold
        AND p.status != 'decommissioned';
    
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
                'threshold_days', 90,
                'excluded_page_types', ARRAY['Product', 'Service_Core']
            )
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update manual decay function
CREATE OR REPLACE FUNCTION execute_silo_decay(threshold_days INTEGER DEFAULT 90)
RETURNS TABLE (
    archived_count INTEGER,
    event_id BIGINT
) AS $$
DECLARE
    archived INTEGER := 0;
    event_id_val BIGINT;
BEGIN
    -- Archive stale proposals (EXCLUDE Product and Service_Core)
    UPDATE pages
    SET 
        status = 'decommissioned',
        decommissioned_at = NOW(),
        is_proposal = false
    WHERE 
        is_proposal = true
        AND (governance_checks->>'page_type') NOT IN ('Product', 'Service_Core', 'product', 'service_core')
        AND created_at < NOW() - (threshold_days || ' days')::INTERVAL
        AND status NOT IN ('published', 'decommissioned');
    
    GET DIAGNOSTICS archived = ROW_COUNT;
    
    -- Archive orphaned pages (EXCLUDE Product and Service_Core)
    UPDATE pages p
    SET 
        status = 'decommissioned',
        decommissioned_at = NOW()
    WHERE 
        p.id NOT IN (SELECT page_id FROM keywords WHERE page_id IS NOT NULL)
        AND p.id NOT IN (SELECT page_id FROM page_silos WHERE page_id IS NOT NULL)
        AND (p.governance_checks->>'page_type') NOT IN ('Product', 'Service_Core', 'product', 'service_core')
        AND p.status = 'draft'
        AND p.created_at < NOW() - (threshold_days || ' days')::INTERVAL
        AND p.status != 'decommissioned';
    
    GET DIAGNOSTICS archived = archived + ROW_COUNT;
    
    -- Log manual decay event
    INSERT INTO system_events (event_type, entity_type, entity_id, payload)
    VALUES (
        'SILO_DECAY_MANUAL',
        'pages',
        NULL,
        jsonb_build_object(
            'threshold_days', threshold_days,
            'archived_count', archived,
            'excluded_page_types', ARRAY['Product', 'Service_Core']
        )
    )
    RETURNING id INTO event_id_val;
    
    RETURN QUERY SELECT archived, event_id_val;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trigger_silo_decay() IS 'Automated cleanup/archival mechanism for stale data (v1.3.1 + V1 Stress Test: excludes Product/Service_Core pages)';
COMMENT ON FUNCTION execute_silo_decay(INTEGER) IS 'Manual execution of decay logic for maintenance (V1 Stress Test: excludes Product/Service_Core pages)';

