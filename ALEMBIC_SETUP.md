# Alembic Setup for Fresh Database

## Overview

Alembic is now configured to auto-generate migrations from your SQLAlchemy models (like Django's `makemigrations`).

## Setup Complete ✅

1. ✅ `alembic.ini` - Configuration file
2. ✅ `alembic/env.py` - Reads your models from `app/db/models.py`
3. ✅ `alembic/versions/` - Directory for migration files
4. ✅ Added `alembic==1.12.1` to `requirements.txt`

## Installation

```bash
pip install alembic
# Or install all dependencies:
pip install -r requirements.txt
```

## Usage for Fresh Database

### Step 1: Generate Initial Migration

```bash
alembic revision --autogenerate -m "initial_schema"
```

**What this does:**
- Reads all your models from `app/db/models.py`
- Compares with your database (which is empty)
- Generates a migration file in `alembic/versions/` with all tables, columns, indexes, etc.

### Step 2: Review Generated Migration

Check the generated file:
```
alembic/versions/xxxxx_initial_schema.py
```

Review it to ensure:
- All tables are included
- Enum types are created correctly
- Indexes and constraints look right

### Step 3: Run Migration

```bash
alembic upgrade head
```

**What this does:**
- Creates all tables, indexes, constraints from your models
- Sets up your complete database schema
- **Just like Django's `python manage.py migrate`**

## Complete Workflow for Fresh DB

```bash
# 1. Install Alembic (if not already installed)
pip install alembic

# 2. Generate migration from all your models
alembic revision --autogenerate -m "initial_schema"

# 3. Review the generated file (optional but recommended)
# Check: alembic/versions/xxxxx_initial_schema.py

# 4. Run migration - creates all tables!
alembic upgrade head

# Done! Your database now has all tables from your models.
```

## For Production

Same process:
```bash
# On production server
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

## Important Notes

1. **Fresh Database Only**: This workflow is for a completely empty database
2. **Model Changes**: If you modify models later, run `alembic revision --autogenerate -m "description"` again
3. **Database URL**: Make sure `.env` has `DATABASE_URL_SYNC` set correctly
4. **Review Migrations**: Always review generated migrations before running them

## Comparison with Django

| Django | Alembic |
|--------|---------|
| `python manage.py makemigrations` | `alembic revision --autogenerate -m "message"` |
| `python manage.py migrate` | `alembic upgrade head` |

## Next Steps

1. **Install**: `pip install alembic`
2. **Generate**: `alembic revision --autogenerate -m "initial_schema"`
3. **Review**: Check the generated file
4. **Run**: `alembic upgrade head`
5. **Done!** All tables created from your models.
