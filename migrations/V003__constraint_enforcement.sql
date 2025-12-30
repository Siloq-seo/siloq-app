-- Siloq Core Database Schema v1.3.1
-- Additional constraint enforcement and validation functions
-- Idempotent migration - safe to run multiple times

-- ============================================================================
-- CONSTRAINT ENFORCEMENT FUNCTIONS
-- ============================================================================

-- Function to enforce silo count limits (3-7 per site)
CREATE OR REPLACE FUNCTION enforce_silo_count()
RETURNS TRIGGER AS $$
DECLARE
    silo_count INTEGER;
BEGIN
    -- Count existing silos for this site
    SELECT COUNT(*) INTO silo_count
    FROM silos
    WHERE site_id = COALESCE(NEW.site_id, OLD.site_id);
    
    -- Check minimum (3 silos)
    IF silo_count < 3 THEN
        RAISE EXCEPTION 'Site must have at least 3 silos. Current count: %', silo_count;
    END IF;
    
    -- Check maximum (7 silos)
    IF silo_count > 7 THEN
        RAISE EXCEPTION 'Site cannot have more than 7 silos. Current count: %', silo_count;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply silo count enforcement (on DELETE, check remaining count)
DROP TRIGGER IF EXISTS trigger_enforce_silo_count ON silos;
CREATE TRIGGER trigger_enforce_silo_count
    AFTER INSERT OR DELETE ON silos
    FOR EACH ROW
    EXECUTE FUNCTION enforce_silo_count();

-- Function to prevent keyword conflicts
-- Ensures a keyword cannot be reassigned to a different page
CREATE OR REPLACE FUNCTION prevent_keyword_reassignment()
RETURNS TRIGGER AS $$
BEGIN
    -- If updating and page_id changes, raise error
    IF OLD IS NOT NULL AND NEW.page_id != OLD.page_id THEN
        RAISE EXCEPTION 'Keyword "%" cannot be reassigned from page % to page %. Keywords have one-to-one mapping with pages.',
            NEW.keyword, OLD.page_id, NEW.page_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply keyword reassignment prevention
DROP TRIGGER IF EXISTS trigger_prevent_keyword_reassignment ON keywords;
CREATE TRIGGER trigger_prevent_keyword_reassignment
    BEFORE UPDATE ON keywords
    FOR EACH ROW
    EXECUTE FUNCTION prevent_keyword_reassignment();

-- Function to validate normalized path format
-- Ensures paths are properly formatted
CREATE OR REPLACE FUNCTION validate_path_format()
RETURNS TRIGGER AS $$
BEGIN
    -- Path must start with /
    IF NEW.path !~ '^/' THEN
        RAISE EXCEPTION 'Path must start with "/". Got: %', NEW.path;
    END IF;
    
    -- Path cannot have consecutive slashes
    IF NEW.path ~ '//' THEN
        RAISE EXCEPTION 'Path cannot contain consecutive slashes. Got: %', NEW.path;
    END IF;
    
    -- Path cannot end with / (except root)
    IF NEW.path != '/' AND NEW.path ~ '/$' THEN
        RAISE EXCEPTION 'Path cannot end with "/" (except root). Got: %', NEW.path;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply path format validation
DROP TRIGGER IF EXISTS trigger_validate_path_format ON pages;
CREATE TRIGGER trigger_validate_path_format
    BEFORE INSERT OR UPDATE ON pages
    FOR EACH ROW
    EXECUTE FUNCTION validate_path_format();

-- Function to prevent orphaned keywords
-- Ensures keywords are deleted when their page is deleted (CASCADE handles this, but we log it)
CREATE OR REPLACE FUNCTION log_keyword_cascade()
RETURNS TRIGGER AS $$
BEGIN
    -- This is informational - CASCADE handles the deletion
    -- But we log it for audit purposes
    IF TG_OP = 'DELETE' THEN
        INSERT INTO system_events (event_type, entity_type, entity_id, payload)
        VALUES (
            'CASCADE_DELETE',
            'keywords',
            NULL,
            jsonb_build_object(
                'deleted_page_id', OLD.id,
                'reason', 'page_deleted'
            )
        );
    END IF;
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Apply keyword cascade logging
DROP TRIGGER IF EXISTS trigger_log_keyword_cascade ON pages;
CREATE TRIGGER trigger_log_keyword_cascade
    BEFORE DELETE ON pages
    FOR EACH ROW
    EXECUTE FUNCTION log_keyword_cascade();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION enforce_silo_count() IS 'Enforces 3-7 silo limit per site at database level';
COMMENT ON FUNCTION prevent_keyword_reassignment() IS 'Prevents keyword reassignment to maintain one-to-one mapping';
COMMENT ON FUNCTION validate_path_format() IS 'Validates path format (starts with /, no consecutive slashes, etc.)';
COMMENT ON FUNCTION log_keyword_cascade() IS 'Logs keyword cascade deletions for audit purposes';

