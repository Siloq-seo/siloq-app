# Fresh Database Setup - One Command

## ✅ Your Migration is Ready!

Your migration file (`20413611c841_initial_schema.py`) is already fixed and ready to use. It includes:
- ✅ pgvector extension creation
- ✅ Enum type creation
- ✅ All tables (users, organizations, sites, pages, etc.)
- ✅ Proper `create_type=False` on all enums
- ✅ Vector column support

## 🚀 Fresh Database Setup (One Command)

### Step 1: Drop alembic_version table (if exists)

```sql
-- Connect to your database and run:
DROP TABLE IF EXISTS alembic_version CASCADE;
```

### Step 2: Run Migration

```bash
alembic upgrade head
```

**That's it!** The migration will:
1. Create pgvector extension
2. Create all enum types
3. Create all tables (users, organizations, sites, pages, etc.)
4. Create all indexes
5. Set up the complete schema

## 📋 Complete Fresh Start Commands

**For Local Development:**
```bash
# 1. Drop alembic_version (if exists)
psql -U your_user -d your_database -c "DROP TABLE IF EXISTS alembic_version CASCADE;"

# 2. Run migration
alembic upgrade head

# 3. Verify
alembic current
```

**For Production (DigitalOcean):**
- The migration runs automatically on app startup
- Just make sure `alembic_version` table is dropped if you're resetting

## ✅ Verification

After migration, check tables exist:
```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

You should see:
- alembic_version
- api_keys
- organizations
- users
- sites
- pages
- silos
- ... (all other tables)

## 🎯 That's It!

Your migration is production-ready and will work in **one go** - no manual fixes needed!
