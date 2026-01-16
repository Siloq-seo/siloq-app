-- Rollback script for V002__silo_decay_trigger.sql

-- Drop triggers
DROP TRIGGER IF EXISTS trigger_pages_silo_decay ON pages;

-- Drop functions
DROP FUNCTION IF EXISTS trigger_silo_decay();
DROP FUNCTION IF EXISTS execute_silo_decay(INTEGER);

