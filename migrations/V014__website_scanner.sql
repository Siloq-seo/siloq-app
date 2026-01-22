-- V014: Website Scanner Table
-- Description: Create scans table to store website SEO scan results

-- Create scans table
CREATE TABLE IF NOT EXISTS scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,  -- Optional: link to existing site
    url TEXT NOT NULL,  -- Website URL that was scanned
    domain TEXT NOT NULL,  -- Extracted domain for easier querying
    
    -- Scan metadata
    scan_type TEXT NOT NULL DEFAULT 'full',  -- 'full', 'quick', 'technical'
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    
    -- Overall score
    overall_score FLOAT,  -- 0.0 to 100.0
    grade TEXT,  -- 'A+', 'A', 'B', 'C', 'D', 'F'
    
    -- Category scores (0.0 to 100.0)
    technical_score FLOAT,
    content_score FLOAT,
    structure_score FLOAT,
    performance_score FLOAT,
    seo_score FLOAT,
    
    -- Detailed results stored as JSONB
    technical_details JSONB DEFAULT '{}'::jsonb,  -- Technical SEO findings
    content_details JSONB DEFAULT '{}'::jsonb,  -- Content quality findings
    structure_details JSONB DEFAULT '{}'::jsonb,  -- Site structure findings
    performance_details JSONB DEFAULT '{}'::jsonb,  -- Performance metrics
    seo_details JSONB DEFAULT '{}'::jsonb,  -- SEO-specific findings
    
    -- Recommendations
    recommendations JSONB DEFAULT '[]'::jsonb,  -- Array of recommendation objects
    
    -- Scan execution
    pages_crawled INTEGER DEFAULT 0,
    scan_duration_seconds INTEGER,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_scan_url_not_empty CHECK (length(trim(url)) > 0),
    CONSTRAINT chk_scan_domain_not_empty CHECK (length(trim(domain)) > 0),
    CONSTRAINT chk_scan_type_valid CHECK (scan_type IN ('full', 'quick', 'technical')),
    CONSTRAINT chk_scan_status_valid CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT chk_overall_score_range CHECK (overall_score IS NULL OR (overall_score >= 0.0 AND overall_score <= 100.0)),
    CONSTRAINT chk_technical_score_range CHECK (technical_score IS NULL OR (technical_score >= 0.0 AND technical_score <= 100.0)),
    CONSTRAINT chk_content_score_range CHECK (content_score IS NULL OR (content_score >= 0.0 AND content_score <= 100.0)),
    CONSTRAINT chk_structure_score_range CHECK (structure_score IS NULL OR (structure_score >= 0.0 AND structure_score <= 100.0)),
    CONSTRAINT chk_performance_score_range CHECK (performance_score IS NULL OR (performance_score >= 0.0 AND performance_score <= 100.0)),
    CONSTRAINT chk_seo_score_range CHECK (seo_score IS NULL OR (seo_score >= 0.0 AND seo_score <= 100.0)),
    CONSTRAINT chk_grade_valid CHECK (grade IS NULL OR grade IN ('A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_scans_domain ON scans(domain);
CREATE INDEX IF NOT EXISTS idx_scans_site_id ON scans(site_id);
CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_overall_score ON scans(overall_score DESC);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_scans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER trigger_scans_updated_at
    BEFORE UPDATE ON scans
    FOR EACH ROW
    EXECUTE FUNCTION update_scans_updated_at();
