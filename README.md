# Siloq - Governance-First AI SEO Platform

A governance engine designed to build structurally perfect websites through constraint-based content generation and authority preservation.

## Core Principles

This is a **governance engine, not a content writer**. Every feature must enforce:
- **Structure**: Content organization and hierarchy
- **Intent**: Purpose and meaning preservation
- **Authority**: Source credibility and trust

## MVP Requirements (8 Weeks)

### Week 1: Database & Structural Guarantees ✅
- ✅ Unique normalized paths (database-level enforcement)
- ✅ Canonical uniqueness (one-to-one keyword mapping)
- ✅ Reverse Silos (3–7) structurally enforced
- ✅ SILO_DECAY trigger for automatic cleanup
- ✅ Comprehensive audit trail (system_events)

### Weeks 2-6: Governance Engine ✅
- ✅ Prevent cannibalization by constraint
- ✅ Govern AI output before, during, and after generation
- ✅ Block unsafe publishing
- ✅ Preserve authority during decommissioning
- ✅ Week 5: AI Draft Engine with structured outputs, retry-cost safety, and enhanced postcheck
- ✅ Week 6: Publish & Lifecycle Gates - All 6 gates must pass before publishing

## Architecture

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with pgvector for semantic similarity
- **Queue**: BullMQ/Redis for asynchronous job processing
- **Schema**: Hybrid JSON-LD generation (backend-driven, not AI-generated)

## Setup

### Week 1: Database Setup

```bash
# Install dependencies
poetry install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Full Week 1 reset (recommended)
siloq reset-week1

# Or step-by-step:
siloq db:bootstrap    # Initialize database
siloq db:migrate       # Run migrations
siloq db:seed          # Seed test data
siloq test:all         # Verify constraints
```

### Development Server

```bash
# Start the server
uvicorn app.main:app --reload
```

### CLI Commands

```bash
# Database management
siloq db:migrate       # Run all migrations
siloq db:reset         # Reset database
siloq db:seed          # Seed test data
siloq db:verify        # Test constraints

# Testing
siloq test:all         # Run all tests
siloq test:uniqueness  # Test uniqueness constraints
siloq test:silo-decay  # Test SILO_DECAY trigger

# Documentation
siloq docs:schema      # Generate schema docs
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system architecture and [SETUP.md](SETUP.md) for setup instructions.

## Project Structure

```
siloq/
├── app/
│   ├── core/           # Core configuration and utilities
│   ├── db/             # Database models
│   ├── governance/     # Governance engine components
│   │   ├── ai_output.py          # AI output governance
│   │   ├── structured_output.py  # Week 5: Structured output generator
│   │   ├── cost_calculator.py     # Week 5: Cost tracking
│   │   ├── lifecycle_gates.py     # Week 6: Lifecycle gate manager
│   │   ├── redirect_manager.py    # Week 6: Redirect enforcement
│   │   └── page_helpers.py        # Page model helper utilities
│   ├── decision/       # Decision engine (preflight/postcheck)
│   ├── queues/         # Redis-based job processors
│   ├── schemas/        # Pydantic schemas and JSON-LD generation
│   ├── services/       # Service layer for business logic
│   ├── api/            # FastAPI routes (organized by domain)
│   │   ├── routes/     # Separate route modules
│   │   ├── dependencies.py        # Dependency injection
│   │   └── exception_handlers.py # Custom exception handlers
│   ├── types.py        # TypedDict type definitions
│   └── exceptions.py   # Custom exception classes
├── migrations/         # SQL migrations (V001-V010)
└── tests/             # Test files
```

## Week 5: AI Draft Engine Features

### Structured Output Generator
- Enforces structured output schema (body, entities, FAQs, links)
- Uses OpenAI structured outputs API with fallback
- Prevents hallucinated links and ensures FAQ schema compliance

### Retry-Cost Safety
- Automatic retries on failures (up to max_retries, default: 3)
- Cost tracking for all AI API calls
- Cost limit enforcement per job (default: $10.0)
- `AI_MAX_RETRY_EXCEEDED` status when retry limit reached

### Enhanced Postcheck
- **Entity Coverage**: Minimum 3 entities required
- **FAQ Minimum**: Minimum 3 FAQs with question + answer
- **Link Validation**: No hallucinated links allowed
- **FAQ Schema**: Each FAQ must have both question and answer fields

### Bulk Job Processing
- Process multiple generation jobs in batch
- Returns summary with job IDs and errors

## Week 6: Publish & Lifecycle Gates

### Lifecycle Gate Manager
- **6 Gates**: All must pass before publishing
  1. Governance checks gate (pre/during/post)
  2. Schema sync validation gate (JSON-LD matches content)
  3. Embedding gate (vector embedding required)
  4. Authority gate (sources required for high authority)
  5. Content structure gate (title, body, path validation)
  6. Status gate (must allow publishing)

### Schema Sync Validation
- Validates JSON-LD schema matches content
- Checks headline, URL path, and dates
- Blocks publishing if schema is out of sync

### Redirect Enforcement
- Validates redirect URLs (internal/external)
- Verifies internal redirect targets exist
- Enforces redirects on decommission
- Stores redirect metadata in governance_checks

### Enhanced Decommission
- Always preserves authority score and source URLs
- Redirect validation and enforcement
- Comprehensive audit logging

## Code Quality Improvements

### Type Safety
- Complete type hints with TypedDict classes
- UUID type consistency throughout
- Type-safe return values

### Error Handling
- Custom exception classes with error codes
- Consistent error response format
- Exception handlers registered in FastAPI

### Architecture
- Dependency injection for all services
- Routes organized by domain (sites, pages, jobs, silos)
- Service layer for business logic
- Centralized configuration

## Development

```bash
# Run tests
pytest

# Format code
black .

# Lint
ruff check .
```

## Recent Changes

- **Week 6**: Publish & Lifecycle Gates - All 6 gates must pass before publishing
- **Week 5**: AI Draft Engine with structured outputs, retry logic, and enhanced postcheck
- **Refactoring**: Comprehensive code quality improvements
  - Type safety with TypedDict classes
  - Custom exception handling
  - Dependency injection
  - Route organization by domain
  - Service layer structure
  - Centralized configuration
- **Database**: Added governance_checks column to pages table (V009), enhanced silo decay logging (V010)
- **API**: Routes split into separate modules (sites, pages, jobs, silos)

