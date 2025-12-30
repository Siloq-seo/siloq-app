-- Week 5: AI Draft Engine - Retry and Cost Tracking
-- Adds retry tracking, cost tracking, and structured output metadata to generation_jobs

-- Add retry tracking columns
ALTER TABLE generation_jobs
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS max_retries INTEGER DEFAULT 3,
ADD COLUMN IF NOT EXISTS total_cost_usd NUMERIC(10, 6) DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS last_retry_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS structured_output_metadata JSONB DEFAULT '{}'::jsonb;

-- Add constraint for retry count
ALTER TABLE generation_jobs
ADD CONSTRAINT chk_retry_count_non_negative CHECK (retry_count >= 0),
ADD CONSTRAINT chk_max_retries_positive CHECK (max_retries > 0),
ADD CONSTRAINT chk_total_cost_non_negative CHECK (total_cost_usd >= 0.0);

-- Add index for retry tracking
CREATE INDEX IF NOT EXISTS idx_generation_jobs_retry_count ON generation_jobs(retry_count, status);

-- Add index for cost tracking
CREATE INDEX IF NOT EXISTS idx_generation_jobs_total_cost ON generation_jobs(total_cost_usd);

-- Update status constraint to include AI_MAX_RETRY_EXCEEDED state
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
        'failed',
        'ai_max_retry_exceeded'
    )
);

-- Add comment
COMMENT ON COLUMN generation_jobs.retry_count IS 'Number of retry attempts for this job';
COMMENT ON COLUMN generation_jobs.max_retries IS 'Maximum number of retries allowed (default: 3)';
COMMENT ON COLUMN generation_jobs.total_cost_usd IS 'Total cost in USD for all AI API calls for this job';
COMMENT ON COLUMN generation_jobs.structured_output_metadata IS 'Metadata from structured output generation (entities, FAQs, links)';

