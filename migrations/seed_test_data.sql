-- Siloq Test Data Seed
-- Creates sample data for testing constraints and functionality
-- Idempotent - safe to run multiple times

-- ============================================================================
-- CLEANUP (for idempotency)
-- ============================================================================

DELETE FROM page_silos;
DELETE FROM keywords;
DELETE FROM pages;
DELETE FROM silos;
DELETE FROM sites;
DELETE FROM system_events;
DELETE FROM cannibalization_checks;
DELETE FROM generation_jobs;

-- ============================================================================
-- SAMPLE SITES
-- ============================================================================

INSERT INTO sites (id, name, domain) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Example SEO Site', 'example-seo.com'),
    ('22222222-2222-2222-2222-222222222222', 'Test Blog', 'test-blog.com')
ON CONFLICT (domain) DO NOTHING;

-- ============================================================================
-- SAMPLE SILOS (3-7 per site, as required)
-- ============================================================================

-- Site 1: 5 silos (valid)
INSERT INTO silos (id, site_id, name, slug, position) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'SEO Basics', 'seo-basics', 1),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11111111-1111-1111-1111-111111111111', 'Advanced SEO', 'advanced-seo', 2),
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', '11111111-1111-1111-1111-111111111111', 'Technical SEO', 'technical-seo', 3),
    ('dddddddd-dddd-dddd-dddd-dddddddddddd', '11111111-1111-1111-1111-111111111111', 'Content Strategy', 'content-strategy', 4),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '11111111-1111-1111-1111-111111111111', 'Link Building', 'link-building', 5)
ON CONFLICT DO NOTHING;

-- Site 2: 3 silos (minimum)
INSERT INTO silos (id, site_id, name, slug, position) VALUES
    ('ffffffff-ffff-ffff-ffff-ffffffffffff', '22222222-2222-2222-2222-222222222222', 'Getting Started', 'getting-started', 1),
    ('gggggggg-gggg-gggg-gggg-gggggggggggg', '22222222-2222-2222-2222-222222222222', 'Tutorials', 'tutorials', 2),
    ('hhhhhhhh-hhhh-hhhh-hhhh-hhhhhhhhhhhh', '22222222-2222-2222-2222-222222222222', 'Resources', 'resources', 3)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SAMPLE PAGES
-- ============================================================================

-- Site 1 pages
INSERT INTO pages (id, site_id, path, title, body, status, authority_score, source_urls, is_proposal) VALUES
    ('10000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', '/what-is-seo', 'What is SEO?', 'SEO stands for Search Engine Optimization...', 'published', 0.8, ARRAY['https://example.com/seo-guide'], false),
    ('10000000-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', '/seo-keywords', 'SEO Keywords Guide', 'Keywords are the foundation of SEO...', 'published', 0.75, ARRAY['https://example.com/keywords'], false),
    ('10000000-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111111', '/on-page-seo', 'On-Page SEO Checklist', 'On-page SEO involves optimizing...', 'approved', 0.7, ARRAY['https://example.com/onpage'], false),
    ('10000000-0000-0000-0000-000000000004', '11111111-1111-1111-1111-111111111111', '/proposed-article', 'Proposed Article Title', 'This is a proposal...', 'draft', 0.0, ARRAY[]::text[], true)
ON CONFLICT DO NOTHING;

-- Site 2 pages
INSERT INTO pages (id, site_id, path, title, body, status, authority_score, source_urls, is_proposal) VALUES
    ('20000000-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', '/welcome', 'Welcome to Test Blog', 'Welcome to our blog...', 'published', 0.6, ARRAY[]::text[], false),
    ('20000000-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222', '/first-post', 'First Blog Post', 'This is our first post...', 'published', 0.5, ARRAY[]::text[], false)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- KEYWORDS (one-to-one mapping)
-- ============================================================================

INSERT INTO keywords (keyword, page_id) VALUES
    ('what is seo', '10000000-0000-0000-0000-000000000001'),
    ('seo keywords', '10000000-0000-0000-0000-000000000002'),
    ('on page seo', '10000000-0000-0000-0000-000000000003'),
    ('welcome', '20000000-0000-0000-0000-000000000001'),
    ('first post', '20000000-0000-0000-0000-000000000002')
ON CONFLICT (keyword) DO NOTHING;

-- ============================================================================
-- PAGE-SILO RELATIONSHIPS
-- ============================================================================

INSERT INTO page_silos (page_id, silo_id) VALUES
    -- Site 1: Pages in silos
    ('10000000-0000-0000-0000-000000000001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'), -- SEO Basics
    ('10000000-0000-0000-0000-000000000002', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'), -- SEO Basics
    ('10000000-0000-0000-0000-000000000003', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'), -- Advanced SEO
    -- Site 2: Pages in silos
    ('20000000-0000-0000-0000-000000000001', 'ffffffff-ffff-ffff-ffff-ffffffffffff'), -- Getting Started
    ('20000000-0000-0000-0000-000000000002', 'ffffffff-ffff-ffff-ffff-ffffffffffff')  -- Getting Started
ON CONFLICT DO NOTHING;

-- ============================================================================
-- VERIFICATION QUERIES (for testing)
-- ============================================================================

-- Verify site structure
DO $$
DECLARE
    site1_silo_count INTEGER;
    site2_silo_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO site1_silo_count FROM silos WHERE site_id = '11111111-1111-1111-1111-111111111111';
    SELECT COUNT(*) INTO site2_silo_count FROM silos WHERE site_id = '22222222-2222-2222-2222-222222222222';
    
    IF site1_silo_count != 5 THEN
        RAISE EXCEPTION 'Site 1 should have 5 silos, found %', site1_silo_count;
    END IF;
    
    IF site2_silo_count != 3 THEN
        RAISE EXCEPTION 'Site 2 should have 3 silos, found %', site2_silo_count;
    END IF;
    
    RAISE NOTICE '✓ Seed data verification passed';
END $$;

