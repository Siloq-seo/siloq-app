# Siloq CLI Quick Reference

## Installation

```bash
# Install dependencies
poetry install

# Make CLI executable (if using direct script)
chmod +x siloq_cli.py
```

## Main Commands

### Week 1 Reset (All-in-One)
```bash
siloq reset-week1
```
Performs complete Week 1 reset: backup → reset → migrate → seed → test → docs

### Database Commands
```bash
siloq db:migrate          # Run all migrations
siloq db:patch-1.3.1      # Apply v1.3.1 patches only
siloq db:reset            # Drop and recreate database
siloq db:bootstrap        # Initialize local dev (uses bootstrap-db.sh)
siloq db:seed             # Seed test data
siloq db:verify           # Test all constraints
```

### Testing Commands
```bash
siloq test:all            # Run all verification tests
siloq test:uniqueness     # Test path/canonical uniqueness
siloq test:keyword-lock   # Test keyword one-to-one mapping
siloq test:silo-decay     # Test SILO_DECAY trigger
```

### Documentation Commands
```bash
siloq docs:schema         # Generate schema documentation
```

## Environment Variables

Required in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname
DATABASE_URL_SYNC=postgresql://user:pass@host:port/dbname
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

## Common Workflows

### First-Time Setup
```bash
# 1. Install dependencies
poetry install

# 2. Set up environment
cp .env.example .env
# Edit .env with your database credentials

# 3. Full reset
siloq reset-week1
```

### Development Reset
```bash
# Quick reset during development
siloq db:reset
siloq db:migrate
siloq db:seed
```

### Verify Constraints
```bash
# Run all tests
siloq test:all

# Or individual tests
siloq test:uniqueness
siloq test:silo-decay
```

### Update Documentation
```bash
# Regenerate schema docs
siloq docs:schema
# Output: docs/SCHEMA.md
```

## Troubleshooting

### Database Connection Issues
- Check `.env` file has correct credentials
- Verify PostgreSQL is running
- Check `DATABASE_URL_SYNC` is set correctly

### Migration Errors
- Ensure database exists
- Check PostgreSQL extensions (uuid-ossp, vector) are installed
- Run `siloq db:reset` to start fresh

### Test Failures
- Ensure migrations are up to date: `siloq db:migrate`
- Check database has test data: `siloq db:seed`
- Verify constraints are properly applied

## Exit Codes

- `0` - Success
- `1` - Error (database connection, migration failure, etc.)

## See Also

- [README.md](README.md) - Main project documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [SETUP.md](SETUP.md) - Setup instructions
- [migrations/README.md](migrations/README.md) - Database schema documentation

