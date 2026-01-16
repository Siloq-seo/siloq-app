-- SQL Tests for Siloq Database Constraints
-- These tests verify that database-level constraints work correctly
-- Run these tests after migrations to verify structural guarantees

-- ============================================================================
-- TEST 1: Duplicate normalized paths are rejected
-- ============================================================================
-- Expected: Second insert should FAIL with unique constraint violation

DO $$
DECLARE
    test_site_id UUID;
    test_page_id_1 UUID;
    test_page_id_2 UUID;
    error_occurred BOOLEAN := false;
BEGIN
    -- Create test site
    INSERT INTO sites (name, domain) 
    VALUES ('Test Site', 'test.example.com')
    RETURNING id INTO test_site_id;
    
    -- Insert first page
    INSERT INTO pages (site_id, path, title) 
    VALUES (test_site_id, '/blog/post-title', 'Post 1')
    RETURNING id INTO test_page_id_1;
    
    -- Try to insert duplicate normalized path (should FAIL)
    BEGIN
        INSERT INTO pages (site_id, path, title) 
        VALUES (test_site_id, '/Blog/Post-Title', 'Post 2');  -- Same normalized path!
        
        RAISE EXCEPTION 'TEST FAILED: Duplicate normalized path was accepted!';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'TEST PASSED: Duplicate normalized path correctly rejected';
            error_occurred := true;
    END;
    
    IF NOT error_occurred THEN
        RAISE EXCEPTION 'TEST FAILED: Expected unique constraint violation';
    END IF;
    
    -- Cleanup
    DELETE FROM sites WHERE id = test_site_id;
    
    RAISE NOTICE '✓ Test 1 PASSED: Duplicate normalized paths are rejected';
END $$;

-- ============================================================================
-- TEST 2: Orphaned keywords cannot exist
-- ============================================================================
-- Expected: Insert should FAIL with foreign key constraint violation

DO $$
DECLARE
    error_occurred BOOLEAN := false;
BEGIN
    -- Try to insert keyword with non-existent page_id (should FAIL)
    BEGIN
        INSERT INTO keywords (keyword, page_id) 
        VALUES ('test-keyword', '00000000-0000-0000-0000-000000000000');
        
        RAISE EXCEPTION 'TEST FAILED: Orphaned keyword was accepted!';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'TEST PASSED: Orphaned keyword correctly rejected';
            error_occurred := true;
    END;
    
    IF NOT error_occurred THEN
        RAISE EXCEPTION 'TEST FAILED: Expected foreign key constraint violation';
    END IF;
    
    RAISE NOTICE '✓ Test 2 PASSED: Orphaned keywords cannot exist';
END $$;

-- ============================================================================
-- TEST 3: Keyword reassignment is prevented
-- ============================================================================
-- Expected: Update should FAIL with trigger exception

DO $$
DECLARE
    test_site_id UUID;
    test_page_id_1 UUID;
    test_page_id_2 UUID;
    error_occurred BOOLEAN := false;
BEGIN
    -- Create test site and pages
    INSERT INTO sites (name, domain) 
    VALUES ('Test Site', 'test2.example.com')
    RETURNING id INTO test_site_id;
    
    INSERT INTO pages (site_id, path, title) 
    VALUES (test_site_id, '/page1', 'Page 1')
    RETURNING id INTO test_page_id_1;
    
    INSERT INTO pages (site_id, path, title) 
    VALUES (test_site_id, '/page2', 'Page 2')
    RETURNING id INTO test_page_id_2;
    
    -- Create keyword
    INSERT INTO keywords (keyword, page_id) 
    VALUES ('test-keyword', test_page_id_1);
    
    -- Try to reassign keyword to different page (should FAIL)
    BEGIN
        UPDATE keywords 
        SET page_id = test_page_id_2 
        WHERE keyword = 'test-keyword';
        
        RAISE EXCEPTION 'TEST FAILED: Keyword reassignment was accepted!';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%cannot be reassigned%' THEN
                RAISE NOTICE 'TEST PASSED: Keyword reassignment correctly prevented';
                error_occurred := true;
            ELSE
                RAISE;
            END IF;
    END;
    
    IF NOT error_occurred THEN
        RAISE EXCEPTION 'TEST FAILED: Expected trigger to prevent reassignment';
    END IF;
    
    -- Cleanup
    DELETE FROM sites WHERE id = test_site_id;
    
    RAISE NOTICE '✓ Test 3 PASSED: Keyword reassignment is prevented';
END $$;

-- ============================================================================
-- TEST 4: Silo count limits are enforced (3-7)
-- ============================================================================
-- Expected: Inserting 8th silo should FAIL

DO $$
DECLARE
    test_site_id UUID;
    i INTEGER;
    error_occurred BOOLEAN := false;
BEGIN
    -- Create test site
    INSERT INTO sites (name, domain) 
    VALUES ('Test Site', 'test3.example.com')
    RETURNING id INTO test_site_id;
    
    -- Create 7 silos (maximum)
    FOR i IN 1..7 LOOP
        INSERT INTO silos (site_id, name, slug, position) 
        VALUES (test_site_id, 'Silo ' || i, 'silo-' || i, i);
    END LOOP;
    
    -- Try to insert 8th silo (should FAIL)
    BEGIN
        INSERT INTO silos (site_id, name, slug, position) 
        VALUES (test_site_id, 'Silo 8', 'silo-8', 8);
        
        RAISE EXCEPTION 'TEST FAILED: 8th silo was accepted!';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%cannot have more than 7 silos%' THEN
                RAISE NOTICE 'TEST PASSED: Silo count limit correctly enforced';
                error_occurred := true;
            ELSE
                RAISE;
            END IF;
    END;
    
    IF NOT error_occurred THEN
        RAISE EXCEPTION 'TEST FAILED: Expected trigger to enforce silo count';
    END IF;
    
    -- Cleanup
    DELETE FROM sites WHERE id = test_site_id;
    
    RAISE NOTICE '✓ Test 4 PASSED: Silo count limits are enforced';
END $$;

-- ============================================================================
-- TEST 5: Path format validation
-- ============================================================================
-- Expected: Invalid paths should be rejected

DO $$
DECLARE
    test_site_id UUID;
    error_count INTEGER := 0;
BEGIN
    -- Create test site
    INSERT INTO sites (name, domain) 
    VALUES ('Test Site', 'test4.example.com')
    RETURNING id INTO test_site_id;
    
    -- Test: Path without leading slash (should FAIL)
    BEGIN
        INSERT INTO pages (site_id, path, title) 
        VALUES (test_site_id, 'no-leading-slash', 'Title');
        RAISE EXCEPTION 'TEST FAILED: Path without leading slash was accepted!';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%must start with%' THEN
                error_count := error_count + 1;
            ELSE
                RAISE;
            END IF;
    END;
    
    -- Test: Path with consecutive slashes (should FAIL)
    BEGIN
        INSERT INTO pages (site_id, path, title) 
        VALUES (test_site_id, '/double//slash', 'Title');
        RAISE EXCEPTION 'TEST FAILED: Path with consecutive slashes was accepted!';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%consecutive slashes%' THEN
                error_count := error_count + 1;
            ELSE
                RAISE;
            END IF;
    END;
    
    -- Test: Path ending with slash (except root) (should FAIL)
    BEGIN
        INSERT INTO pages (site_id, path, title) 
        VALUES (test_site_id, '/trailing-slash/', 'Title');
        RAISE EXCEPTION 'TEST FAILED: Path ending with slash was accepted!';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%cannot end with%' THEN
                error_count := error_count + 1;
            ELSE
                RAISE;
            END IF;
    END;
    
    -- Verify all three tests passed
    IF error_count != 3 THEN
        RAISE EXCEPTION 'TEST FAILED: Expected 3 path validation errors, got %', error_count;
    END IF;
    
    -- Cleanup
    DELETE FROM sites WHERE id = test_site_id;
    
    RAISE NOTICE '✓ Test 5 PASSED: Path format validation works';
END $$;

-- ============================================================================
-- TEST 6: System events are logged
-- ============================================================================
-- Expected: Every INSERT/UPDATE/DELETE should create a system event

DO $$
DECLARE
    test_site_id UUID;
    event_count_before INTEGER;
    event_count_after INTEGER;
BEGIN
    -- Count events before
    SELECT COUNT(*) INTO event_count_before FROM system_events;
    
    -- Create site (should trigger event)
    INSERT INTO sites (name, domain) 
    VALUES ('Test Site', 'test5.example.com')
    RETURNING id INTO test_site_id;
    
    -- Count events after
    SELECT COUNT(*) INTO event_count_after FROM system_events;
    
    IF event_count_after <= event_count_before THEN
        RAISE EXCEPTION 'TEST FAILED: System event was not logged for INSERT';
    END IF;
    
    -- Update site (should trigger event)
    UPDATE sites SET name = 'Updated Name' WHERE id = test_site_id;
    
    SELECT COUNT(*) INTO event_count_after FROM system_events;
    
    IF event_count_after <= event_count_before + 1 THEN
        RAISE EXCEPTION 'TEST FAILED: System event was not logged for UPDATE';
    END IF;
    
    -- Cleanup
    DELETE FROM sites WHERE id = test_site_id;
    
    RAISE NOTICE '✓ Test 6 PASSED: System events are logged';
END $$;

-- ============================================================================
-- TEST 7: One-to-one keyword mapping
-- ============================================================================
-- Expected: Second keyword for same page should FAIL

DO $$
DECLARE
    test_site_id UUID;
    test_page_id UUID;
    error_occurred BOOLEAN := false;
BEGIN
    -- Create test site and page
    INSERT INTO sites (name, domain) 
    VALUES ('Test Site', 'test6.example.com')
    RETURNING id INTO test_site_id;
    
    INSERT INTO pages (site_id, path, title) 
    VALUES (test_site_id, '/page', 'Page')
    RETURNING id INTO test_page_id;
    
    -- Create first keyword
    INSERT INTO keywords (keyword, page_id) 
    VALUES ('keyword1', test_page_id);
    
    -- Try to create second keyword for same page (should FAIL)
    BEGIN
        INSERT INTO keywords (keyword, page_id) 
        VALUES ('keyword2', test_page_id);
        
        RAISE EXCEPTION 'TEST FAILED: Second keyword for same page was accepted!';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'TEST PASSED: One-to-one mapping correctly enforced';
            error_occurred := true;
    END;
    
    IF NOT error_occurred THEN
        RAISE EXCEPTION 'TEST FAILED: Expected unique constraint violation';
    END IF;
    
    -- Cleanup
    DELETE FROM sites WHERE id = test_site_id;
    
    RAISE NOTICE '✓ Test 7 PASSED: One-to-one keyword mapping enforced';
END $$;

-- ============================================================================
-- SUMMARY
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'ALL CONSTRAINT TESTS COMPLETED';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'If all tests passed, your database constraints are working correctly!';
    RAISE NOTICE '';
END $$;

