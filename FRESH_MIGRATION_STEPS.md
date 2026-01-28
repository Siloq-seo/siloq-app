# Fresh Migration Generation Steps

## Step 1: Clean Database State

You need to tell Alembic the database is empty. Choose one:

### Option A: Drop alembic_version table (if exists)
```sql
-- Connect to your database and run:
DROP TABLE IF EXISTS alembic_version CASCADE;
```

### Option B: Stamp as base (via Alembic)
```bash
alembic stamp base
```

## Step 2: Generate Fresh Migration

```bash
alembic revision --autogenerate -m "initial_schema"
```

This will:
- Auto-detect all your models
- Generate the migration file
- Auto-fix it via post_write_hook (pgvector, enums, etc.)

## Step 3: Apply Migration

```bash
alembic upgrade head
```

## All-in-One Command (if database is truly empty)

```bash
# 1. Stamp as base
alembic stamp base

# 2. Generate
alembic revision --autogenerate -m "initial_schema"

# 3. Apply
alembic upgrade head
```
