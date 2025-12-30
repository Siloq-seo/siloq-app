# Siloq Setup Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ with pgvector extension
- Redis 6+

## Installation

### 1. Install Python Dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using poetry
poetry install
```

### 2. Setup PostgreSQL with pgvector

```bash
# Install pgvector extension
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Create database
createdb siloq
```

### 3. Setup Redis

```bash
# Start Redis server
redis-server

# Or using Docker
docker run -d -p 6379:6379 redis:latest
```

### 4. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings:
# - DATABASE_URL
# - DATABASE_URL_SYNC
# - REDIS_URL
# - OPENAI_API_KEY
# - SECRET_KEY
# - AI_MAX_RETRIES (default: 3)
# - AI_MAX_COST_PER_JOB_USD (default: 10.0)
# - MIN_FAQ_COUNT (default: 3)
# - MIN_ENTITY_COUNT (default: 3)
```

### 5. Setup Database

**Option A: Using Bootstrap Script (Recommended)**

```bash
# Set PostgreSQL superuser password
export POSTGRES_PASSWORD=your_postgres_password

# Run bootstrap script (creates DB, user, and runs migrations)
./scripts/bootstrap-db.sh
```

The bootstrap script will:
- Create database and user
- Run all migrations in order (V001-V010)
- Set up proper permissions
- Output connection strings for your `.env` file

**Option B: Manual Setup**

```bash
# Create database
createdb siloq

# Run migrations in order
psql -U postgres -d siloq -f migrations/V001__initial_schema.sql
psql -U postgres -d siloq -f migrations/V002__silo_decay_trigger.sql
psql -U postgres -d siloq -f migrations/V003__constraint_enforcement.sql
psql -U postgres -d siloq -f migrations/V004__decision_engine_states.sql
psql -U postgres -d siloq -f migrations/V005__pgvector_setup.sql
psql -U postgres -d siloq -f migrations/V006__reservation_system.sql
psql -U postgres -d siloq -f migrations/V007__reverse_silo_engine.sql
psql -U postgres -d siloq -f migrations/V008__week5_ai_draft_engine.sql
psql -U postgres -d siloq -f migrations/V009__add_governance_checks_to_pages.sql
psql -U postgres -d siloq -f migrations/V010__week6_lifecycle_gates.sql
```

**Note:** The schema uses raw SQL migrations for better control over database-level constraints. See `migrations/README.md` for full documentation.

### 6. Start the Application

```bash
# Development server
python run.py

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Architecture Overview

### Core Components

1. **Governance Engine** (`app/governance/`)
   - Cannibalization detection using pgvector
   - Reverse Silos enforcement (3-7 silos)
   - AI output governance (pre/during/post generation)
   - Publishing safety checks

2. **Queue System** (`app/queues/`)
   - Redis-based job queue
   - Asynchronous content generation
   - Job status tracking

3. **Database Models** (`app/db/models.py`)
   - Sites, Silos, Pages (refactored from Content)
   - Vector embeddings for similarity
   - Governance checks stored in JSONB
   - SystemEvent audit logs

4. **JSON-LD Generation** (`app/schemas/jsonld.py`)
   - Backend-driven schema generation
   - Structured data for SEO

### API Endpoints

- `POST /api/v1/sites` - Create site
- `POST /api/v1/sites/{site_id}/silos` - Create silo (enforces 3-7 limit)
- `POST /api/v1/pages/{page_id}/validate` - Validate page (preflight check)
- `POST /api/v1/pages` - Create page and queue generation
- `GET /api/v1/pages/{page_id}` - Get page
- `GET /api/v1/pages/{page_id}/jsonld` - Get JSON-LD schema
- `GET /api/v1/pages/{page_id}/gates` - Check all lifecycle gates (Week 6)
- `POST /api/v1/pages/{page_id}/publish` - Publish page (with 6 lifecycle gates - Week 6)
- `POST /api/v1/pages/{page_id}/decommission` - Decommission with authority preservation and redirect enforcement (Week 6)
- `GET /api/v1/jobs/{job_id}` - Get job status (includes retry count and cost)

## Governance Flow

1. **Pre-Generation**: Validate structure, check cannibalization, verify silos
2. **During Generation**: Monitor output quality, intent preservation
3. **Post-Generation**: Final cannibalization check, authority validation, entity coverage, FAQ minimum, link validation (Week 5)
4. **Publishing**: 6 lifecycle gates must all pass (Week 6)
   - Governance checks gate
   - Schema sync validation gate
   - Embedding gate
   - Authority gate
   - Content structure gate
   - Status gate
5. **Decommissioning**: Preserve authority data, validate and enforce redirects (Week 6)

## Week 5: AI Draft Engine Features

- **Structured Outputs**: AI generates content with enforced schema (body, entities, FAQs, links)
- **Retry Logic**: Automatic retries on failures (up to max_retries, default: 3)
- **Cost Tracking**: Tracks all AI API costs per job with limit enforcement
- **Bulk Jobs**: Process multiple generation jobs in batch
- **Enhanced Postcheck**: 
  - Entity coverage (minimum 3 entities)
  - FAQ minimum (minimum 3 FAQs with question + answer)
  - Link validation (no hallucinated links)

## Week 6: Publish & Lifecycle Gates

- **Lifecycle Gate Manager**: 6 gates must all pass before publishing
- **Schema Sync Validation**: JSON-LD schema must match content
- **Redirect Enforcement**: Validates and enforces redirects on decommission
- **Enhanced Decommission**: Always preserves authority with redirect support

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=app
```

## Development

```bash
# Format code
black .

# Lint
ruff check .

# Type check
mypy app
```

## Production Deployment

1. Set `ENVIRONMENT=production` in `.env`
2. Use proper database connection pooling
3. Configure Redis persistence
4. Set up proper logging
5. Use Alembic for all database changes
6. Configure CORS appropriately
7. Set up monitoring and alerting

