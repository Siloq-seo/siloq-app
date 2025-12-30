-- Rollback script for V003__constraint_enforcement.sql

-- Drop triggers
DROP TRIGGER IF EXISTS trigger_enforce_silo_count ON silos;
DROP TRIGGER IF EXISTS trigger_prevent_keyword_reassignment ON keywords;
DROP TRIGGER IF EXISTS trigger_validate_path_format ON pages;
DROP TRIGGER IF EXISTS trigger_log_keyword_cascade ON pages;

-- Drop functions
DROP FUNCTION IF EXISTS enforce_silo_count();
DROP FUNCTION IF EXISTS prevent_keyword_reassignment();
DROP FUNCTION IF EXISTS validate_path_format();
DROP FUNCTION IF EXISTS log_keyword_cascade();

