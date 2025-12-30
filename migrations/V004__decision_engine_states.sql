-- Siloq Decision Engine - Week 2
-- State machine and job state extensions
-- Idempotent migration - safe to run multiple times

-- ============================================================================
-- UPDATE GENERATION_JOBS TABLE
-- ============================================================================

-- Add new columns for state machine
ALTER TABLE generation_jobs
    ADD COLUMN IF NOT EXISTS error_code TEXT,
    ADD COLUMN IF NOT EXISTS state_transition_history JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS preflight_approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS prompt_locked_at TIMESTAMPTZ;

-- Update status constraint to include new states
ALTER TABLE generation_jobs
    DROP CONSTRAINT IF EXISTS chk_job_status_valid;

ALTER TABLE generation_jobs
    ADD CONSTRAINT chk_job_status_valid CHECK (
        status IN (
            'draft',
            'preflight_approved',
            'prompt_locked',
            'processing',
            'postcheck_passed',
            'postcheck_failed',
            'completed',
            'failed'
        )
    );

-- Update existing jobs to 'draft' if they're in old states
UPDATE generation_jobs
SET status = 'draft'
WHERE status NOT IN (
    'draft',
    'preflight_approved',
    'prompt_locked',
    'processing',
    'postcheck_passed',
    'postcheck_failed',
    'completed',
    'failed'
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_generation_jobs_error_code ON generation_jobs(error_code);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_preflight_approved_at ON generation_jobs(preflight_approved_at);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_prompt_locked_at ON generation_jobs(prompt_locked_at);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN generation_jobs.status IS 'Job state: draft → preflight_approved → prompt_locked → processing → postcheck_passed/failed → completed/failed';
COMMENT ON COLUMN generation_jobs.error_code IS 'Standardized error code from ErrorCodeDictionary (e.g., PREFLIGHT_001)';
COMMENT ON COLUMN generation_jobs.state_transition_history IS 'JSON array of state transitions for audit trail';
COMMENT ON COLUMN generation_jobs.preflight_approved_at IS 'Timestamp when preflight validation passed';
COMMENT ON COLUMN generation_jobs.prompt_locked_at IS 'Timestamp when prompt was locked for generation';

