# Siloq Database Schema - Quick Reference

## Bootstrap Database

```bash
export POSTGRES_PASSWORD=your_password
./scripts/bootstrap-db.sh
```

## Run Migrations Manually

```bash
# Connect to database
psql -U siloq_user -d siloq

# Or run from command line (in order)
psql -U siloq_user -d siloq -f migrations/V001__initial_schema.sql
psql -U siloq_user -d siloq -f migrations/V002__silo_decay_trigger.sql
psql -U siloq_user -d siloq -f migrations/V003__constraint_enforcement.sql
psql -U siloq_user -d siloq -f migrations/V004__decision_engine_states.sql
psql -U siloq_user -d siloq -f migrations/V005__pgvector_setup.sql
psql -U siloq_user -d siloq -f migrations/V006__reservation_system.sql
psql -U siloq_user -d siloq -f migrations/V007__reverse_silo_engine.sql
psql -U siloq_user -d siloq -f migrations/V008__week5_ai_draft_engine.sql
psql -U siloq_user -d siloq -f migrations/V009__add_governance_checks_to_pages.sql
psql -U siloq_user -d siloq -f migrations/V010__week6_lifecycle_gates.sql
```

## Test Constraints

```bash
psql -U siloq_user -d siloq -f tests/test_constraints.sql
```

## Common Operations

### Find page by path
```sql
SELECT * FROM pages 
WHERE site_id = '...' 
  AND normalized_path = lower(trim('/blog/post'));
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

### Execute manual SILO_DECAY
```sql
SELECT * FROM execute_silo_decay(threshold_days => 90);
```

### View recent system events
```sql
SELECT * FROM system_events 
ORDER BY created_at DESC 
LIMIT 20;
```

### Check generation job retries and costs (Week 5)
```sql
SELECT 
    id, 
    status, 
    retry_count, 
    max_retries, 
    total_cost_usd,
    error_code
FROM generation_jobs 
WHERE status = 'ai_max_retry_exceeded' 
   OR total_cost_usd > 5.0
ORDER BY total_cost_usd DESC;
```

### View governance checks for a page
```sql
SELECT 
    id, 
    title, 
    governance_checks->'pre_generation' as pre_gen,
    governance_checks->'during_generation' as during_gen,
    governance_checks->'post_generation' as post_gen,
    governance_checks->'decommission' as decommission,
    governance_checks->'published' as published
FROM pages 
WHERE id = '...';
```

### View redirect information for decommissioned pages (Week 6)
```sql
SELECT 
    id,
    title,
    path,
    governance_checks->'decommission'->>'redirect_to' as redirect_to,
    governance_checks->'decommission'->>'is_internal_redirect' as is_internal
FROM pages 
WHERE status = 'decommissioned'
  AND governance_checks->'decommission'->>'redirect_to' IS NOT NULL;
```

## Key Constraints

- ✅ **Normalized paths are unique per site** - Prevents duplicate paths
- ✅ **Keywords have one-to-one mapping with pages** - No ambiguity
- ✅ **Silos limited to 3-7 per site** - Enforced at database level
- ✅ **All changes logged to system_events** - Immutable audit trail
- ✅ **Path format validated** - Must start with `/`, no consecutive slashes
- ✅ **Generation jobs track retries and costs** - Week 5: Retry limit and cost tracking
- ✅ **Pages store governance checks** - Week 5: JSONB column for governance check results
- ✅ **Enhanced silo decay logging** - Week 6: Comprehensive logging with page details
- ✅ **Redirect tracking** - Week 6: Redirect information stored in governance_checks

## Rollback (⚠️ DESTRUCTIVE)

```bash
# Rollback in reverse order
psql -U siloq_user -d siloq -f migrations/rollback/V003__rollback.sql
psql -U siloq_user -d siloq -f migrations/rollback/V002__rollback.sql
psql -U siloq_user -d siloq -f migrations/rollback/V001__rollback.sql
```

## Environment Variables

```bash
DB_NAME=siloq
DB_USER=siloq_user
DB_PASSWORD=siloq_password
DB_HOST=localhost
DB_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password
```

## Connection Strings

**Sync (psycopg2):**
```
postgresql://siloq_user:siloq_password@localhost:5432/siloq
```

**Async (asyncpg):**
```
postgresql+asyncpg://siloq_user:siloq_password@localhost:5432/siloq
```

