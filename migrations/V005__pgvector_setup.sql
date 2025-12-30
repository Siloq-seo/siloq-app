-- Siloq Week 3: pgvector Setup and Optimization
-- Vector similarity index optimization for cannibalization detection
-- Idempotent migration - safe to run multiple times

-- ============================================================================
-- PGVECTOR EXTENSION
-- ============================================================================

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- VECTOR INDEX OPTIMIZATION
-- ============================================================================

-- Drop existing index if it exists (to recreate with optimized parameters)
DROP INDEX IF EXISTS idx_pages_embedding;

-- Create optimized vector index for similarity search
-- Using ivfflat with cosine distance operator
-- Lists parameter: 100 (good for datasets with 100K-1M vectors)
-- Adjust based on actual dataset size: lists = rows / 1000 (minimum 10)
CREATE INDEX idx_pages_embedding ON pages 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ============================================================================
-- VECTOR DIMENSION VALIDATION
-- ============================================================================

-- Function to validate embedding dimensions
CREATE OR REPLACE FUNCTION validate_embedding_dimension()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if embedding exists and has correct dimensions (1536 for OpenAI)
    IF NEW.embedding IS NOT NULL THEN
        IF array_length(NEW.embedding::float[], 1) != 1536 THEN
            RAISE EXCEPTION 'Embedding must have exactly 1536 dimensions. Got: %', 
                array_length(NEW.embedding::float[], 1);
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply dimension validation trigger
DROP TRIGGER IF EXISTS trigger_validate_embedding_dimension ON pages;
CREATE TRIGGER trigger_validate_embedding_dimension
    BEFORE INSERT OR UPDATE ON pages
    FOR EACH ROW
    WHEN (NEW.embedding IS NOT NULL)
    EXECUTE FUNCTION validate_embedding_dimension();

-- ============================================================================
-- PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Set index scan parameters for better performance
-- These are session-level settings, but we document them here
-- Consider setting in postgresql.conf for production:
-- SET ivfflat.probes = 10;  -- Default, adjust based on accuracy vs speed needs

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON INDEX idx_pages_embedding IS 'Optimized vector index for cosine similarity search (ivfflat, lists=100)';
COMMENT ON FUNCTION validate_embedding_dimension() IS 'Validates embedding has exactly 1536 dimensions (OpenAI text-embedding-3-small)';

