# Fix "Target database is not up to date" Error

## The Problem

Alembic won't generate new migrations if it thinks the database has pending migrations. This happens when:
- `alembic_version` table exists with old revision
- Database has tables but no matching migration

## Solution for Fresh Database

### Option 1: Drop alembic_version table (Recommended)

```sql
-- Connect to your database and run:
DROP TABLE IF EXISTS alembic_version CASCADE;
```

Then run:
```bash
alembic revision --autogenerate -m "initial_schema"
```

### Option 2: Stamp database as empty

```bash
# Tell Alembic the database is at "base" (no migrations)
alembic stamp base

# Then generate
alembic revision --autogenerate -m "initial_schema"
```

### Option 3: Force autogenerate (bypass check)

```bash
# Use --sql flag to see what would be generated (doesn't require DB to be up to date)
alembic revision --autogenerate -m "initial_schema" --sql

# Or manually create migration without autogenerate
alembic revision -m "initial_schema"
# Then manually write the upgrade() function
```

## Quick Fix Command

**For completely fresh database:**
```bash
# 1. Drop alembic_version (in your database)
# psql -U your_user -d your_database -c "DROP TABLE IF EXISTS alembic_version CASCADE;"

# 2. Generate migration
alembic revision --autogenerate -m "initial_schema"

# 3. Apply it
alembic upgrade head
```
