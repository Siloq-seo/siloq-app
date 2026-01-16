-- Rollback script for V001__initial_schema.sql
-- WARNING: This will drop all tables and data

-- Drop triggers first
DROP TRIGGER IF EXISTS trigger_pages_updated_at ON pages;
DROP TRIGGER IF EXISTS trigger_sites_updated_at ON sites;
DROP TRIGGER IF EXISTS trigger_silos_updated_at ON silos;
DROP TRIGGER IF EXISTS trigger_sites_system_events ON sites;
DROP TRIGGER IF EXISTS trigger_pages_system_events ON pages;
DROP TRIGGER IF EXISTS trigger_keywords_system_events ON keywords;
DROP TRIGGER IF EXISTS trigger_silos_system_events ON silos;

-- Drop functions
DROP FUNCTION IF EXISTS update_updated_at_column();
DROP FUNCTION IF EXISTS log_system_event();

-- Drop tables (in reverse dependency order)
DROP TABLE IF EXISTS generation_jobs CASCADE;
DROP TABLE IF EXISTS cannibalization_checks CASCADE;
DROP TABLE IF EXISTS page_silos CASCADE;
DROP TABLE IF EXISTS keywords CASCADE;
DROP TABLE IF EXISTS pages CASCADE;
DROP TABLE IF EXISTS silos CASCADE;
DROP TABLE IF EXISTS sites CASCADE;
DROP TABLE IF EXISTS system_events CASCADE;

-- Drop extensions (optional - comment out if other schemas use them)
-- DROP EXTENSION IF EXISTS "vector";
-- DROP EXTENSION IF EXISTS "uuid-ossp";

