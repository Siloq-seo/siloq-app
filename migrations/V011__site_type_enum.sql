-- Correction Sprint: Task 1 - Site Type Enum
-- Add site_type enum and required fields based on site type
-- Idempotent migration - safe to run multiple times

-- Create site_type enum
DO $$ BEGIN
    CREATE TYPE site_type_enum AS ENUM ('LOCAL_SERVICE', 'ECOMMERCE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add site_type column to sites table
ALTER TABLE sites 
    ADD COLUMN IF NOT EXISTS site_type site_type_enum;

-- Add LOCAL_SERVICE required fields
ALTER TABLE sites
    ADD COLUMN IF NOT EXISTS geo_coordinates JSONB,
    ADD COLUMN IF NOT EXISTS service_area JSONB;

-- Add ECOMMERCE required fields
ALTER TABLE sites
    ADD COLUMN IF NOT EXISTS product_sku_pattern TEXT,
    ADD COLUMN IF NOT EXISTS currency_settings JSONB;

-- Add constraints for LOCAL_SERVICE sites
-- Note: We can't use CHECK constraints with conditional logic easily in PostgreSQL
-- So we'll enforce this in application logic (preflight_validator)
-- But we can add comments for documentation
COMMENT ON COLUMN sites.site_type IS 'Site type: LOCAL_SERVICE requires geo_coordinates and service_area; ECOMMERCE requires product_sku_pattern and currency_settings';
COMMENT ON COLUMN sites.geo_coordinates IS 'Required for LOCAL_SERVICE: JSONB with lat/lng coordinates, e.g., {"lat": 30.2672, "lng": -97.7431}';
COMMENT ON COLUMN sites.service_area IS 'Required for LOCAL_SERVICE: JSONB array of service areas, e.g., ["Austin", "Round Rock", "Cedar Park"]';
COMMENT ON COLUMN sites.product_sku_pattern IS 'Required for ECOMMERCE: Pattern for product SKUs, e.g., "PROD-{category}-{id}"';
COMMENT ON COLUMN sites.currency_settings IS 'Required for ECOMMERCE: JSONB with currency config, e.g., {"default": "USD", "supported": ["USD", "EUR"]}';

