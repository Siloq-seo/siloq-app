# Siloq Project Structure

## Directory Organization

### Root Level

```
siloq/
├── app/                    # Main application code
├── tests/                  # Test files
├── migrations/             # Database migrations
├── scripts/                # Utility scripts
├── docs/                   # Documentation
├── wordpress-plugin/        # WordPress plugin code
├── archive/                # Archived code (alembic)
├── README.md               # Main project README
├── LICENSE                 # License file
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Poetry configuration
├── pytest.ini             # Pytest configuration
├── Procfile               # Process file for deployment
├── app.yaml               # App configuration
├── runtime.txt            # Python runtime version
├── run.py                 # Main application entry point
├── run_migration.py       # Migration runner
└── siloq_cli.py           # CLI entry point
```

### Application Structure (`app/`)

```
app/
├── __init__.py
├── main.py                 # FastAPI application
├── types.py                # Type definitions
├── exceptions.py           # Custom exceptions
├── api/                    # API layer
│   ├── routes/            # Route modules (by domain)
│   ├── dependencies.py    # Dependency injection
│   ├── exception_handlers.py
│   └── helpers.py         # API utilities
├── core/                   # Core functionality
│   ├── config.py          # Configuration
│   ├── database.py        # Database setup
│   ├── auth.py            # Authentication
│   ├── redis.py           # Redis client
│   ├── rate_limit.py      # Rate limiting
│   ├── billing/           # Billing/entitlements
│   └── security/          # Security modules
├── db/                     # Database layer
│   ├── models.py          # SQLAlchemy models
│   └── enums.py           # Database enums
├── governance/            # Governance engine
│   ├── ai/                # AI governance
│   ├── content/           # Content quality
│   ├── structure/         # Structural governance
│   ├── seo/               # SEO governance
│   ├── lifecycle/         # Lifecycle management
│   ├── authority/         # Authority management
│   ├── sync/              # Synchronization
│   ├── monitoring/        # Monitoring
│   ├── future/            # Future features
│   └── utils/             # Governance utilities
├── decision/              # Decision engine
├── queues/                # Queue system
├── schemas/               # Pydantic schemas
├── services/              # Business logic services
├── utils/                 # Shared utilities
└── cli/                   # CLI commands
```

### Documentation Structure (`docs/`)

```
docs/
├── README.md              # Documentation index
├── setup/                 # Setup guides
│   ├── QUICK_START.md
│   ├── SETUP.md
│   ├── DIGITALOCEAN_SETUP_GUIDE.md
│   ├── DIGITALOCEAN_DEPLOYMENT_GUIDE.md
│   └── DEPLOYMENT_INSTRUCTIONS.md
├── guides/                # User guides
│   ├── HOW_TO_GENERATE_TOKEN.md
│   ├── QUICK_TOKEN_GENERATION.md
│   ├── GENERATE_TOKEN.md
│   ├── FIX_ZSH_PIP_ISSUE.md
│   └── ENV_FILE_CHECK.md
├── integration/           # Integration guides
│   ├── WORDPRESS_INTEGRATION_GUIDE.md
│   └── WORDPRESS_TALI_IMPLEMENTATION.md
├── architecture/         # Architecture docs
│   ├── ARCHITECTURE.md
│   └── PROJECT_STRUCTURE.md (this file)
└── reference/             # Reference documentation
    ├── CLI_QUICK_REFERENCE.md
    ├── QUICK_START_DIGITALOCEAN.md
    ├── READY_TO_DEPLOY.md
    └── ... (other reference docs)
```

### Scripts Structure (`scripts/`)

```
scripts/
├── bootstrap-db.sh        # Database bootstrap
├── generate_token.py      # Token generation
├── install_jose.sh        # Dependency installation
├── setup_digitalocean.sh  # DigitalOcean setup
└── check_table.py         # Database table checker
```

### Tests Structure (`tests/`)

```
tests/
├── conftest.py           # Pytest configuration
├── unit/                 # Unit tests
│   ├── api/
│   ├── core/
│   └── governance/
└── integration/          # Integration tests
    └── api/
```

### Migrations Structure (`migrations/`)

```
migrations/
├── V001__*.sql           # Versioned migrations
├── rollback/             # Rollback scripts
├── seed_test_data.sql    # Test data
├── README.md             # Migration docs
└── QUICK_REFERENCE.md    # Quick reference
```

## File Organization Principles

1. **Separation of Concerns**: Each module has a clear responsibility
2. **Domain-Driven**: Routes organized by domain (sites, pages, silos)
3. **Layered Architecture**: Clear separation between API, services, and data layers
4. **Documentation**: All docs in `docs/` organized by category
5. **Scripts**: All utility scripts in `scripts/`
6. **Tests**: Tests mirror application structure

## Key Directories

- **app/core/** - Core infrastructure (config, database, auth)
- **app/governance/** - Governance engine (organized by domain)
- **app/api/routes/** - API endpoints (organized by resource)
- **app/services/** - Business logic layer
- **app/utils/** - Shared utilities
- **docs/** - All documentation
- **scripts/** - Utility scripts
- **tests/** - Test files

## Naming Conventions

- **Python files**: snake_case.py
- **Classes**: PascalCase
- **Functions**: snake_case
- **Constants**: UPPER_SNAKE_CASE
- **Migrations**: V###__description.sql
- **Tests**: test_*.py

## Entry Points

- **run.py** - Main FastAPI application
- **siloq_cli.py** - CLI command interface
- **run_migration.py** - Database migration runner

## Scripts Usage

All utility scripts are in `scripts/` directory:

```bash
# Generate JWT token
python3 scripts/generate_token.py

# Install dependencies
./scripts/install_jose.sh

# Setup DigitalOcean
./scripts/setup_digitalocean.sh

# Check database table
python3 scripts/check_table.py

# Bootstrap database
./scripts/bootstrap-db.sh
```
