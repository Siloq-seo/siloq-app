-- Siloq Week 3: Reservation System
-- Content slot reservations for planning collision prevention
-- Idempotent migration - safe to run multiple times

-- ============================================================================
-- RESERVATIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS content_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    intent_hash TEXT NOT NULL,
    location TEXT,
    page_id UUID REFERENCES pages(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fulfilled_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT chk_intent_hash_not_empty CHECK (length(trim(intent_hash)) > 0),
    CONSTRAINT chk_reservation_not_expired CHECK (expires_at > created_at)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_reservations_site_id ON content_reservations(site_id);
CREATE INDEX IF NOT EXISTS idx_reservations_intent_hash ON content_reservations(site_id, intent_hash);
CREATE INDEX IF NOT EXISTS idx_reservations_location ON content_reservations(site_id, location) WHERE location IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reservations_expires_at ON content_reservations(expires_at);
CREATE INDEX IF NOT EXISTS idx_reservations_page_id ON content_reservations(page_id) WHERE page_id IS NOT NULL;

-- ============================================================================
-- UNIQUE CONSTRAINT
-- ============================================================================

-- Prevent duplicate active reservations for same intent+location
CREATE UNIQUE INDEX IF NOT EXISTS idx_reservations_active_unique 
ON content_reservations(site_id, intent_hash, location)
WHERE expires_at > NOW() AND fulfilled_at IS NULL;

-- ============================================================================
-- CLEANUP FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_expired_reservations()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete expired and unfulfilled reservations
    DELETE FROM content_reservations
    WHERE expires_at < NOW() AND fulfilled_at IS NULL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE content_reservations IS 'Content slot reservations to prevent planning collisions';
COMMENT ON COLUMN content_reservations.intent_hash IS 'MD5 hash of content intent (title + location)';
COMMENT ON COLUMN content_reservations.location IS 'Geographic location for geo-aware reservations';
COMMENT ON COLUMN content_reservations.expires_at IS 'Reservation expiration timestamp';
COMMENT ON COLUMN content_reservations.fulfilled_at IS 'Timestamp when reservation was fulfilled (page created)';
COMMENT ON FUNCTION cleanup_expired_reservations() IS 'Cleans up expired reservations (call via scheduled job)';

