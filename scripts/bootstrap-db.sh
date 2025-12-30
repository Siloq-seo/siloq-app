#!/bin/bash
# Siloq Database Bootstrap Script
# Sets up PostgreSQL database, user, and schema for local development
# Works on macOS, Linux, and Docker environments

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values (can be overridden by environment variables)
DB_NAME="${DB_NAME:-siloq}"
DB_USER="${DB_USER:-siloq_user}"
DB_PASSWORD="${DB_PASSWORD:-siloq_password}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
MIGRATIONS_DIR="$PROJECT_ROOT/migrations"

echo -e "${GREEN}=== Siloq Database Bootstrap ===${NC}"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "Host: $DB_HOST:$DB_PORT"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: psql command not found. Please install PostgreSQL.${NC}"
    exit 1
fi

# Function to run SQL command
run_sql() {
    PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d postgres -c "$1"
}

# Function to run SQL file
run_sql_file() {
    PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$DB_NAME" -f "$1"
}

# Check if database exists
echo -e "${YELLOW}Checking if database exists...${NC}"
if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${YELLOW}Database '$DB_NAME' already exists.${NC}"
    read -p "Do you want to drop and recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Dropping existing database...${NC}"
        run_sql "DROP DATABASE IF EXISTS $DB_NAME;"
    else
        echo -e "${GREEN}Using existing database.${NC}"
    fi
fi

# Create database if it doesn't exist
if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${YELLOW}Creating database '$DB_NAME'...${NC}"
    run_sql "CREATE DATABASE $DB_NAME;"
    echo -e "${GREEN}Database created.${NC}"
fi

# Create user if it doesn't exist
echo -e "${YELLOW}Checking if user exists...${NC}"
if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    echo -e "${YELLOW}Creating user '$DB_USER'...${NC}"
    run_sql "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
    echo -e "${GREEN}User created.${NC}"
else
    echo -e "${YELLOW}User '$DB_USER' already exists. Updating password...${NC}"
    run_sql "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
fi

# Grant privileges
echo -e "${YELLOW}Granting privileges...${NC}"
run_sql "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
run_sql "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;"

# Connect to the database and grant schema privileges
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$DB_NAME" <<EOF
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

echo -e "${GREEN}Privileges granted.${NC}"

# Run migrations in order
echo -e "${YELLOW}Running migrations...${NC}"
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo -e "${RED}Error: Migrations directory not found: $MIGRATIONS_DIR${NC}"
    exit 1
fi

# Find and sort migration files
MIGRATION_FILES=$(find "$MIGRATIONS_DIR" -name "V*.sql" -type f | sort)

if [ -z "$MIGRATION_FILES" ]; then
    echo -e "${RED}Error: No migration files found in $MIGRATIONS_DIR${NC}"
    exit 1
fi

for migration_file in $MIGRATION_FILES; do
    echo -e "${YELLOW}Running migration: $(basename $migration_file)...${NC}"
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration_file"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Migration completed: $(basename $migration_file)${NC}"
    else
        echo -e "${RED}✗ Migration failed: $(basename $migration_file)${NC}"
        exit 1
    fi
done

echo ""
echo -e "${GREEN}=== Bootstrap Complete ===${NC}"
echo ""
echo "Database connection string:"
echo "  postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "For async SQLAlchemy:"
echo "  postgresql+asyncpg://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "Update your .env file with these values:"
echo "  DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo "  DATABASE_URL_SYNC=postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""

