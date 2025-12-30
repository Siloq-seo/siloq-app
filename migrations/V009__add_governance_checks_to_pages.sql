-- Week 5 Refactor: Add governance_checks column to pages table
-- This supports storing governance check results directly on pages

ALTER TABLE pages
ADD COLUMN IF NOT EXISTS governance_checks JSONB DEFAULT '{}'::jsonb;

-- Add GIN index for efficient JSONB queries
CREATE INDEX IF NOT EXISTS idx_pages_governance_checks 
ON pages USING GIN (governance_checks);

COMMENT ON COLUMN pages.governance_checks IS 'Stores governance check results (pre_generation, during_generation, post_generation)';

