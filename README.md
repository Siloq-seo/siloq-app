# Siloq - Governance-First AI SEO Platform

A governance engine designed to build structurally perfect websites through constraint-based content generation and authority preservation.

## Core Principles

This is a **governance engine, not a content writer**. Every feature must enforce:
- **Structure**: Content organization and hierarchy
- **Intent**: Purpose and meaning preservation
- **Authority**: Source credibility and trust

## MVP Requirements (8 Weeks)

### Week 1: Database & Structural Guarantees
- Unique normalized paths with database-level enforcement
- Canonical uniqueness through one-to-one keyword mapping
- Reverse Silos (3–7) with structural enforcement
- SILO_DECAY trigger for automated content cleanup
- Comprehensive audit trail via system_events

### Weeks 2-6: Governance Engine
- Cannibalization prevention through constraint enforcement
- AI output governance across pre-generation, during-generation, and post-generation stages
- Publishing safety controls to block unsafe content
- Authority preservation during content decommissioning
- Week 5: AI Draft Engine featuring structured outputs, retry-cost safety mechanisms, and enhanced postcheck validation
- Week 6: Publish & Lifecycle Gates requiring all 6 gates to pass before publishing

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
The structured output generator enforces a predefined schema for AI-generated content, including body text, entities, FAQs, and links. It utilizes OpenAI's structured outputs API with automatic fallback mechanisms. The system prevents hallucinated links and ensures strict FAQ schema compliance.

### Retry-Cost Safety
The system implements automatic retry mechanisms for failed generation attempts, configurable up to a maximum retry count (default: 3). All AI API calls are tracked for cost analysis, with per-job cost limits enforced (default: $10.0). Jobs exceeding retry limits are marked with the `AI_MAX_RETRY_EXCEEDED` status.

### Enhanced Postcheck Validation
Post-generation validation includes:
- **Entity Coverage**: Minimum of 3 entities required per content piece
- **FAQ Minimum**: Minimum of 3 FAQs, each with both question and answer fields
- **Link Validation**: Strict validation to prevent hallucinated or invalid links
- **FAQ Schema Enforcement**: Each FAQ item must contain both question and answer fields

### Bulk Job Processing
The system supports batch processing of multiple content generation jobs, returning comprehensive summaries including job IDs and any processing errors.

## Week 6: Publish & Lifecycle Gates

### Lifecycle Gate Manager
The lifecycle gate manager enforces six mandatory gates that must all pass before content can be published:
1. **Governance Checks Gate**: Validates pre-generation, during-generation, and post-generation governance checks
2. **Schema Sync Validation Gate**: Ensures JSON-LD schema matches the actual content
3. **Embedding Gate**: Requires vector embedding for cannibalization tracking
4. **Authority Gate**: Enforces source URL requirements for high-authority content
5. **Content Structure Gate**: Validates title, body, and path structure requirements
6. **Status Gate**: Verifies content status allows publishing

### Schema Sync Validation
The schema sync validation ensures JSON-LD structured data remains synchronized with content. It validates headline, URL path, and date fields, blocking publication if any discrepancies are detected.

### Redirect Enforcement
Redirect enforcement validates both internal and external redirect URLs. For internal redirects, the system verifies that target pages exist and are published. Redirect metadata is stored in the governance_checks field for audit purposes.

### Enhanced Decommission
The decommission process preserves authority scores and source URLs, validates and enforces redirects, and maintains comprehensive audit logs for all decommissioned content.

## Code Quality Improvements

### Type Safety
The codebase implements comprehensive type safety through TypedDict classes, ensuring UUID type consistency across all modules and providing type-safe return values throughout the application.

### Error Handling
Custom exception classes with standardized error codes provide consistent error handling. All exceptions follow a uniform response format and are registered with FastAPI's exception handling system.

### Architecture
The architecture employs dependency injection for all service components, organizes routes by domain (sites, pages, jobs, silos), implements a service layer for business logic separation, and maintains centralized configuration management.

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

- **Week 6**: Implemented Publish & Lifecycle Gates requiring all 6 gates to pass before publishing
- **Week 5**: Deployed AI Draft Engine with structured outputs, retry logic, and enhanced postcheck validation
- **Refactoring**: Comprehensive code quality improvements including:
  - Type safety implementation with TypedDict classes
  - Custom exception handling framework
  - Dependency injection architecture
  - Domain-based route organization
  - Service layer structure
  - Centralized configuration management
- **Database**: Added governance_checks column to pages table (V009), enhanced silo decay logging (V010)
- **API**: Reorganized routes into separate modules by domain (sites, pages, jobs, silos)

