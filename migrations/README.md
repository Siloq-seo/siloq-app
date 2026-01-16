# Siloq Core Database Schema v1.1 + v1.3.1 Patches

## Overview

This document describes the **Siloq Core Database Schema** with absolute structural integrity. The schema is designed to make data cannibalization and corruption **architecturally impossible** through database-level constraints, triggers, and functions.

## Core Principles

1. **Unique normalized paths**: No duplicate or conflicting path entries per site
2. **Canonical uniqueness**: One source of truth for each entity
3. **Keyword → Page one-to-one mapping**: Each keyword maps to exactly one page, no ambiguity
4. **Database-level enforcement**: Business rules enforced at the database layer, not just application code
5. **Immutable audit trails**: All schema changes logged to `system_events`

## Entity-Relationship Diagram

```mermaid
erDiagram
    sites ||--o{ pages : "has"
    sites ||--o{ silos : "has"
    pages ||--o| keywords : "maps_to"
    pages }o--o{ silos : "belongs_to"
    pages ||--o{ cannibalization_checks : "checked_against"
    pages ||--o{ generation_jobs : "generated_by"
    
    sites {
        uuid id PK
        text name
        text domain UK
        timestamptz created_at
        timestamptz updated_at
    }
    
    pages {
        uuid id PK
        uuid site_id FK
        text path
        text normalized_path UK
        text title
        text body
        boolean is_proposal
        text status
        float authority_score
        jsonb source_urls
        vector embedding
        timestamptz created_at
        timestamptz updated_at
        timestamptz published_at
        timestamptz decommissioned_at
    }
    
    keywords {
        text keyword PK
        uuid page_id FK UK
        timestamptz created_at
    }
    
    silos {
        uuid id PK
        uuid site_id FK
        text name
        text slug
        integer position
        timestamptz created_at
        timestamptz updated_at
    }
    
    page_silos {
        uuid page_id PK FK
        uuid silo_id PK FK
        timestamptz created_at
    }
    
    system_events {
        bigserial id PK
        text event_type
        text entity_type
        uuid entity_id
        jsonb payload
        timestamptz created_at
    }
    
    cannibalization_checks {
        uuid id PK
        uuid page_id FK
        uuid compared_with_id FK
        float similarity_score
        boolean threshold_exceeded
        timestamptz created_at
    }
    
    generation_jobs {
        uuid id PK
        uuid page_id FK
        text job_id UK
        text status
        text error_message
        timestamptz created_at
        timestamptz started_at
        timestamptz completed_at
    }
```

## Table Documentation

### `sites`

Top-level website entities.

**Columns:**
- `id` (UUID, PK): Primary key
- `name` (TEXT, NOT NULL): Site name
- `domain` (TEXT, NOT NULL, UNIQUE): Site domain (unique across all sites)
- `created_at` (TIMESTAMPTZ): Creation timestamp
- `updated_at` (TIMESTAMPTZ): Last update timestamp (auto-updated)

**Constraints:**
- `chk_site_name_not_empty`: Name cannot be empty or whitespace
- `chk_site_domain_not_empty`: Domain cannot be empty or whitespace
- `uniq_site_domain`: Domain must be unique

**Rationale:** Ensures each site has a valid, unique domain identifier.

---

### `pages`

Core content pages with normalized path enforcement. This is the **heart of the schema**.

**Columns:**
- `id` (UUID, PK): Primary key
- `site_id` (UUID, FK → sites.id): Parent site
- `path` (TEXT, NOT NULL): Original path (e.g., "/blog/post-title")
- `normalized_path` (TEXT, GENERATED): Automatically generated as `lower(trim(path))`
- `title` (TEXT, NOT NULL): Page title
- `body` (TEXT): Page content
- `is_proposal` (BOOLEAN, DEFAULT false): **v1.3.1** - Flag to distinguish proposed vs. active entries
- `status` (TEXT, DEFAULT 'draft'): Status (draft, pending_review, approved, published, decommissioned, blocked)
- `authority_score` (FLOAT, DEFAULT 0.0): Authority score (0.0-1.0)
- `source_urls` (JSONB, DEFAULT []): Array of source URLs for authority tracking
- `governance_checks` (JSONB, DEFAULT {}): **V009** - Stores governance check results (pre_generation, during_generation, post_generation, safety_check, decommission, published). **V010** - Enhanced to support redirect tracking and lifecycle gate results
- `embedding` (VECTOR(1536)): Vector embedding for cannibalization detection
- `created_at`, `updated_at`, `published_at`, `decommissioned_at` (TIMESTAMPTZ): Timestamps

**Constraints:**
- `chk_page_path_not_empty`: Path cannot be empty
- `chk_page_title_not_empty`: Title cannot be empty
- `chk_page_status_valid`: Status must be one of the allowed values
- `chk_authority_score_range`: Authority score must be between 0.0 and 1.0
- **`uniq_page_normalized_path_per_site`**: **CRITICAL** - Normalized path must be unique per site. This prevents duplicate paths like "/blog/post" and "/Blog/Post" from existing simultaneously.

**Indexes:**
- `idx_pages_site_id`: Foreign key index
- `idx_pages_normalized_path`: For path lookups
- `idx_pages_status`: For status filtering
- `idx_pages_is_proposal`: For proposal filtering
- `idx_pages_embedding`: Vector similarity index (IVFFlat)
- `idx_pages_governance_checks`: GIN index for JSONB queries (V009)

**Rationale:** The normalized path constraint is the **core structural guarantee**. It ensures that no two pages on the same site can have conflicting paths, preventing cannibalization at the database level.

---

### `keywords`

Keywords with **one-to-one mapping** to pages. Each keyword maps to exactly one page.

**Columns:**
- `keyword` (TEXT, PK): Normalized keyword (lowercase, trimmed)
- `page_id` (UUID, FK → pages.id, UNIQUE): Associated page
- `created_at` (TIMESTAMPTZ): Creation timestamp

**Constraints:**
- `chk_keyword_not_empty`: Keyword cannot be empty
- `chk_keyword_normalized`: Keyword must be normalized (lowercase, trimmed)
- **UNIQUE constraint on `page_id`**: Ensures one-to-one mapping. Each keyword maps to exactly one page, and each page can have at most one keyword.

**Indexes:**
- `idx_keywords_page_id`: Foreign key index

**Rationale:** The one-to-one mapping ensures canonical uniqueness. A keyword like "best coffee maker" can only point to one page, eliminating ambiguity.

**Important:** The `UNIQUE` constraint on `page_id` means:
- ✅ One keyword → One page (enforced by PK on `keyword`)
- ✅ One page → At most one keyword (enforced by UNIQUE on `page_id`)

---

### `silos`

Reverse silo structure (3-7 per site). Position-based ordering.

**Columns:**
- `id` (UUID, PK): Primary key
- `site_id` (UUID, FK → sites.id): Parent site
- `name` (TEXT, NOT NULL): Silo name
- `slug` (TEXT, NOT NULL): URL slug
- `position` (INTEGER, NOT NULL): Order within site (1-7)
- `created_at`, `updated_at` (TIMESTAMPTZ): Timestamps

**Constraints:**
- `chk_silo_name_not_empty`: Name cannot be empty
- `chk_silo_slug_not_empty`: Slug cannot be empty
- `chk_silo_position_range`: Position must be between 1 and 7
- `uniq_silo_position_per_site`: Position must be unique per site
- `uniq_silo_slug_per_site`: Slug must be unique per site

**Indexes:**
- `idx_silos_site_id`: Foreign key index
- `idx_silos_position`: For position-based queries

**Rationale:** Enforces the reverse silo structure (3-7 silos per site) at the database level. The position constraint ensures no duplicate positions.

**Trigger:** `enforce_silo_count()` ensures a site always has between 3 and 7 silos.

---

### `page_silos`

Many-to-many relationship between pages and silos.

**Columns:**
- `page_id` (UUID, FK → pages.id): Page reference
- `silo_id` (UUID, FK → silos.id): Silo reference
- `created_at` (TIMESTAMPTZ): Creation timestamp

**Constraints:**
- Composite primary key on `(page_id, silo_id)`: Prevents duplicate associations

**Rationale:** Allows pages to belong to multiple silos while maintaining referential integrity.

---

### `system_events`

Comprehensive audit logging for all schema changes (**v1.3.1 patch**).

**Columns:**
- `id` (BIGSERIAL, PK): Primary key
- `event_type` (TEXT, NOT NULL): Event type (INSERT, UPDATE, DELETE, SILO_DECAY, etc.)
- `entity_type` (TEXT, NOT NULL): Table name
- `entity_id` (UUID): Entity ID (if applicable)
- `payload` (JSONB, DEFAULT {}): Event payload (old/new values, metadata)
- `created_at` (TIMESTAMPTZ): Event timestamp

**Constraints:**
- `chk_event_type_not_empty`: Event type cannot be empty
- `chk_entity_type_not_empty`: Entity type cannot be empty

**Indexes:**
- `idx_system_events_entity`: For entity lookups
- `idx_system_events_created_at`: For time-based queries
- `idx_system_events_type`: For event type filtering

**Rationale:** Provides immutable audit trail for all database changes. Every INSERT, UPDATE, DELETE, and trigger action is logged.

**Triggers:** Automatically logs all changes to `sites`, `pages`, `keywords`, and `silos`.

---

### `cannibalization_checks`

Records of similarity checks between pages.

**Columns:**
- `id` (UUID, PK): Primary key
- `page_id` (UUID, FK → pages.id): Page being checked
- `compared_with_id` (UUID, FK → pages.id): Page compared against
- `similarity_score` (FLOAT, NOT NULL): Similarity score (0.0-1.0)
- `threshold_exceeded` (BOOLEAN, DEFAULT false): Whether threshold was exceeded
- `created_at` (TIMESTAMPTZ): Check timestamp

**Constraints:**
- `chk_similarity_score_range`: Similarity score must be between 0.0 and 1.0
- `chk_no_self_comparison`: Page cannot be compared with itself

**Indexes:**
- `idx_cannibalization_page_id`: For page lookups
- `idx_cannibalization_compared_with`: For comparison lookups
- `idx_cannibalization_created_at`: For time-based queries

**Rationale:** Tracks all cannibalization checks for audit and analysis.

---

### `generation_jobs`

AI content generation job tracking with retry and cost tracking (Week 5).

**Columns:**
- `id` (UUID, PK): Primary key
- `page_id` (UUID, FK → pages.id): Associated page
- `job_id` (TEXT, UNIQUE): External job ID (e.g., BullMQ)
- `status` (TEXT, DEFAULT 'draft'): Job status (draft, preflight_approved, prompt_locked, processing, postcheck_passed, postcheck_failed, completed, failed, ai_max_retry_exceeded)
- `error_message` (TEXT): Error message if failed
- `error_code` (TEXT): Error code from ErrorCodeDictionary
- `retry_count` (INTEGER, DEFAULT 0): Number of retry attempts (Week 5)
- `max_retries` (INTEGER, DEFAULT 3): Maximum retries allowed (Week 5)
- `total_cost_usd` (NUMERIC(10,6), DEFAULT 0.0): Total cost in USD for all AI API calls (Week 5)
- `last_retry_at` (TIMESTAMPTZ): Timestamp of last retry (Week 5)
- `structured_output_metadata` (JSONB): Metadata from structured output (entities, FAQs, links) (Week 5)
- `state_transition_history` (JSONB): State transition history
- `created_at`, `started_at`, `completed_at`, `preflight_approved_at`, `prompt_locked_at` (TIMESTAMPTZ): Timestamps

**Constraints:**
- `chk_job_status_valid`: Status must be one of the allowed values
- `chk_job_id_not_empty`: Job ID cannot be empty

**Indexes:**
- `idx_generation_jobs_page_id`: Foreign key index
- `idx_generation_jobs_status`: For status filtering
- `idx_generation_jobs_job_id`: For job ID lookups

**Rationale:** Tracks AI generation jobs with retry logic, cost tracking, and structured output metadata.

**Week 5 Enhancements:**
- Retry tracking with automatic retry on failures
- Cost tracking for all AI API calls
- Structured output metadata storage
- AI_MAX_RETRY_EXCEEDED status when retry limit reached

---

## Triggers and Functions

### `update_updated_at_column()`

Automatically updates the `updated_at` timestamp on row updates.

**Applied to:** `sites`, `pages`, `silos`

---

### `log_system_event()`

Logs all INSERT, UPDATE, DELETE operations to `system_events`.

**Applied to:** `sites`, `pages`, `keywords`, `silos`

**Payload:** Contains both `old` and `new` row values in JSONB format.

---

### `trigger_silo_decay()` (**v1.3.1**)

Automated cleanup/archival mechanism for stale data.

**Behavior:**
- Archives stale proposals (older than 90 days) by setting `status = 'decommissioned'` and `is_proposal = false`
- Archives orphaned pages (no keyword, no silo, older than 90 days)
- Logs all decay actions to `system_events`

**Applied to:** `pages` (AFTER INSERT OR UPDATE)

**Manual execution:** `SELECT * FROM execute_silo_decay(threshold_days => 90);`

---

### `enforce_silo_count()`

Enforces 3-7 silo limit per site at the database level.

**Behavior:**
- Raises exception if site has fewer than 3 silos
- Raises exception if site has more than 7 silos

**Applied to:** `silos` (AFTER INSERT OR DELETE)

---

### `prevent_keyword_reassignment()`

Prevents keyword reassignment to maintain one-to-one mapping.

**Behavior:**
- Raises exception if attempting to change `page_id` for an existing keyword

**Applied to:** `keywords` (BEFORE UPDATE)

---

### `validate_path_format()`

Validates path format.

**Rules:**
- Path must start with `/`
- Path cannot contain consecutive slashes (`//`)
- Path cannot end with `/` (except root `/`)

**Applied to:** `pages` (BEFORE INSERT OR UPDATE)

---

### `log_keyword_cascade()`

Logs keyword cascade deletions when pages are deleted.

**Applied to:** `pages` (BEFORE DELETE)

---

## Migration Workflow

### Running Migrations

Migrations are located in `/migrations` and are numbered sequentially:
- `V001__initial_schema.sql`: Core schema
- `V002__silo_decay_trigger.sql`: SILO_DECAY trigger
- `V003__constraint_enforcement.sql`: Additional constraints
- `V004__decision_engine_states.sql`: Decision engine state machine
- `V005__pgvector_setup.sql`: pgvector extension setup
- `V006__reservation_system.sql`: Content reservation system
- `V007__reverse_silo_engine.sql`: Reverse silo engine (Week 4)
- `V008__week5_ai_draft_engine.sql`: Week 5 - Retry and cost tracking
- `V009__add_governance_checks_to_pages.sql`: Add governance_checks column to pages
- `V010__week6_lifecycle_gates.sql`: Week 6 - Enhanced silo decay logging and redirect tracking

**Using bootstrap script (recommended):**
```bash
./scripts/bootstrap-db.sh
```

**Manual execution:**
```bash
# Set environment variables
export DB_NAME=siloq
export DB_USER=siloq_user
export DB_PASSWORD=siloq_password
export POSTGRES_PASSWORD=postgres_password

# Run migrations in order
psql -U $DB_USER -d $DB_NAME -f migrations/V001__initial_schema.sql
psql -U $DB_USER -d $DB_NAME -f migrations/V002__silo_decay_trigger.sql
psql -U $DB_USER -d $DB_NAME -f migrations/V003__constraint_enforcement.sql
```

### Rollback

Rollback scripts are in `/migrations/rollback/`:
- `V001__rollback.sql`: Drops all tables
- `V002__rollback.sql`: Removes SILO_DECAY trigger
- `V003__rollback.sql`: Removes constraint enforcement triggers

**⚠️ WARNING:** Rollback scripts will drop data. Use with caution.

---

## Common Queries and Patterns

### Find pages by normalized path
```sql
SELECT * FROM pages 
WHERE site_id = '...' 
  AND normalized_path = lower(trim('/blog/post-title'));
```

### Find keyword's page
```sql
SELECT p.* FROM pages p
JOIN keywords k ON k.page_id = p.id
WHERE k.keyword = 'best coffee maker';
```

### Check for duplicate paths (should return 0)
```sql
SELECT site_id, normalized_path, COUNT(*) 
FROM pages 
GROUP BY site_id, normalized_path 
HAVING COUNT(*) > 1;
```

### Find orphaned pages (no keyword, no silo)
```sql
SELECT p.* FROM pages p
WHERE p.id NOT IN (SELECT page_id FROM keywords WHERE page_id IS NOT NULL)
  AND p.id NOT IN (SELECT page_id FROM page_silos WHERE page_id IS NOT NULL);
```

### Get all system events for a page
```sql
SELECT * FROM system_events
WHERE entity_type = 'pages' 
  AND entity_id = '...'
ORDER BY created_at DESC;
```

### Execute manual SILO_DECAY
```sql
SELECT * FROM execute_silo_decay(threshold_days => 90);
```

### Check silo count per site
```sql
SELECT s.id, s.name, COUNT(si.id) as silo_count
FROM sites s
LEFT JOIN silos si ON si.site_id = s.id
GROUP BY s.id, s.name
HAVING COUNT(si.id) < 3 OR COUNT(si.id) > 7;
```

---

## Testing Constraints

### Test: Duplicate normalized paths are rejected
```sql
-- This should FAIL
INSERT INTO pages (site_id, path, title) 
VALUES 
  ('site-uuid', '/blog/post', 'Post 1'),
  ('site-uuid', '/Blog/Post', 'Post 2');  -- Same normalized path!
```

### Test: Orphaned keywords cannot exist
```sql
-- This should FAIL (page doesn't exist)
INSERT INTO keywords (keyword, page_id) 
VALUES ('test', '00000000-0000-0000-0000-000000000000');
```

### Test: Keyword reassignment is prevented
```sql
-- This should FAIL
UPDATE keywords 
SET page_id = 'different-page-uuid' 
WHERE keyword = 'existing-keyword';
```

### Test: Silo count limits are enforced
```sql
-- This should FAIL if site already has 7 silos
INSERT INTO silos (site_id, name, slug, position) 
VALUES ('site-uuid', 'Silo 8', 'silo-8', 8);
```

### Test: Path format validation
```sql
-- These should all FAIL
INSERT INTO pages (site_id, path, title) VALUES ('site-uuid', 'no-leading-slash', 'Title');
INSERT INTO pages (site_id, path, title) VALUES ('site-uuid', '/double//slash', 'Title');
INSERT INTO pages (site_id, path, title) VALUES ('site-uuid', '/trailing-slash/', 'Title');
```

---

## Environment Variables

The bootstrap script uses these environment variables (with defaults):

- `DB_NAME`: Database name (default: `siloq`)
- `DB_USER`: Database user (default: `siloq_user`)
- `DB_PASSWORD`: Database password (default: `siloq_password`)
- `DB_HOST`: Database host (default: `localhost`)
- `DB_PORT`: Database port (default: `5432`)
- `POSTGRES_USER`: PostgreSQL superuser (default: `postgres`)
- `POSTGRES_PASSWORD`: PostgreSQL superuser password (required)

---

## Success Criteria

✅ **DB enforces structure without UI**: Try to insert bad data via raw SQL—it must fail  
✅ **Bad states are impossible by default**: No orphans, no duplicates, no nulls where data is required  
✅ **All migrations run cleanly** on fresh DB and against existing v1.0 schema  
✅ **Bootstrap script works** on macOS, Linux, and Docker environments  
✅ **100% of constraints documented** in this README  

---

## Version History

- **v1.1**: Initial schema with core structural guarantees
- **v1.3.1**: Added `is_proposal` field, `system_events` table, and `SILO_DECAY` trigger
- **v1.4**: Decision engine state machine (V004)
- **v1.5**: Week 4 - Reverse silo engine with authority funnels (V007)
- **v1.6**: Week 5 - AI Draft Engine with structured outputs, retry logic, and cost tracking (V008, V009)
- **v1.7**: Week 6 - Publish & Lifecycle Gates with redirect enforcement and enhanced silo decay logging (V010)

---

## Support

For questions or issues, refer to:
- `ARCHITECTURE.md`: System architecture overview
- `SETUP.md`: Setup instructions
- Migration files: Inline comments explain each constraint

