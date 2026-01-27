# Running Migrations on DigitalOcean App Platform

## Current Setup ✅

**Migrations run automatically on app startup** - No manual commands needed!

Your `app/main.py` has been configured to run Alembic migrations automatically when the app starts.

## How It Works

1. **App starts** → `lifespan()` function runs
2. **Alembic runs** → `alembic upgrade head` executes automatically
3. **Migrations applied** → All pending migrations are applied
4. **App continues** → Server starts normally

## For Fresh Database (First Deployment)

### Option 1: Automatic (Current Setup) ✅

**Nothing to do!** Migrations run automatically on startup.

When you deploy:
1. App starts
2. Alembic detects empty database
3. Runs all migrations from `alembic/versions/`
4. Creates all tables
5. App is ready

### Option 2: Manual (If Needed)

If you need to run migrations manually:

1. **Via DigitalOcean Console:**
   - Go to your App → Settings → Console
   - Run: `alembic upgrade head`

2. **Via SSH (if enabled):**
   ```bash
   ssh your-app
   alembic upgrade head
   ```

## Environment Variables Required

Make sure these are set in DigitalOcean Dashboard:

- `DATABASE_URL` - Your PostgreSQL connection string (async)
- `DATABASE_URL_SYNC` - Same database but sync connection (for Alembic)
- `ENVIRONMENT=production`

**Important:** `DATABASE_URL_SYNC` must be set! Alembic needs it.

## Migration Tracking

Alembic automatically tracks which migrations have been applied in the `alembic_version` table. This means:
- ✅ Migrations only run once
- ✅ Safe to restart app (won't re-run migrations)
- ✅ Can deploy multiple instances (only first one runs migrations)

## Production Best Practices

### Recommended: Automatic (Current Setup)

✅ **Pros:**
- No manual steps
- Migrations run before app accepts requests
- Works with multiple instances

⚠️ **Cons:**
- Slightly slower startup (if many migrations)
- All instances try to run migrations (but only one succeeds)

### Alternative: Separate Migration Job

If you want more control, you can:

1. **Create a separate job in `app.yaml`:**
   ```yaml
   jobs:
     - name: migrate
       run_command: alembic upgrade head
       instance_count: 1
   ```

2. **Run job before deploying app**

## Troubleshooting

### Migrations Not Running?

1. Check `DATABASE_URL_SYNC` is set in environment variables
2. Check app logs for migration errors
3. Verify Alembic is installed: `pip install alembic`

### Migration Errors?

1. Check logs in DigitalOcean Dashboard → Runtime Logs
2. Verify database connection string is correct
3. Ensure database is accessible from App Platform

## Summary

**For your current setup:**
- ✅ Migrations run **automatically** on app startup
- ✅ No manual commands needed
- ✅ Works on every deployment
- ✅ Safe for production

**Just deploy and it works!** 🚀
