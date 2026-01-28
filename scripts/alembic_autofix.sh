#!/bin/bash
# Auto-generate and fix Alembic migration
# Usage: ./scripts/alembic_autofix.sh "migration_description"

if [ -z "$1" ]; then
    echo "Usage: ./scripts/alembic_autofix.sh 'migration_description'"
    exit 1
fi

# Generate migration
alembic revision --autogenerate -m "$1"

# Get the latest migration file
LATEST_MIGRATION=$(ls -t db_migrations/versions/*.py | head -1)

# Check if it's an initial migration
if grep -q "down_revision = None" "$LATEST_MIGRATION"; then
    echo "Initial migration detected - auto-fixing..."
    python scripts/fix_alembic_migration.py "$LATEST_MIGRATION" --initial
else
    echo "Regular migration - fixing common issues..."
    python scripts/fix_alembic_migration.py "$LATEST_MIGRATION"
fi

echo "✓ Migration generated and fixed: $LATEST_MIGRATION"
