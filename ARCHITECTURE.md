# Siloq Architecture

## Overview

Siloq is a **Governance-First AI SEO Platform** that enforces structure, intent, and authority at every stage of content generation. This is a governance engine, not a content writer.

## Core Principles

Every feature must enforce:
- **Structure**: Content organization and hierarchy
- **Intent**: Purpose and meaning preservation  
- **Authority**: Source credibility and trust

## MVP Requirements (8 Weeks)

✅ **Prevent cannibalization by constraint** - Vector embeddings detect semantic similarity
✅ **Enforce Reverse Silos (3–7) structurally** - Hard limits on silo count per site
✅ **Govern AI output before, during, and after generation** - Three-stage governance
✅ **Block unsafe publishing** - Comprehensive safety checks with 6 lifecycle gates (Week 6)
✅ **Preserve authority during decommissioning** - Maintain source URLs and authority scores with redirect enforcement (Week 6)

## System Architecture

### 1. Database Layer (PostgreSQL + pgvector)

**Models:**
- `Site` - Website entity
- `Silo` - Reverse Silos (3-7 per site, enforced)
- `Page` - Content pages with vector embeddings (refactored from Content)
- `GenerationJob` - AI generation job tracking with retry/cost tracking (Week 5)
- `CannibalizationCheck` - Similarity detection records
- `SystemEvent` - Comprehensive audit log for all governance actions

**Key Features:**
- Vector embeddings (1536 dimensions) for semantic similarity
- Status tracking (DRAFT, PENDING_REVIEW, APPROVED, PUBLISHED, DECOMMISSIONED, BLOCKED)
- Authority score and source URL preservation
- Governance checks stored in JSONB column (Week 5)
- Retry and cost tracking for AI generation jobs (Week 5)

### 2. Governance Engine

#### Cannibalization Prevention (`app/governance/cannibalization.py`)
- Uses pgvector cosine similarity
- Configurable threshold (default: 0.85)
- Blocks content that would cannibalize existing published content
- Records all similarity checks for audit

#### Reverse Silos Enforcement (`app/governance/reverse_silos.py`)
- Hard limits: 3-7 silos per site
- Position-based ordering
- Structural validation before content creation
- Prevents adding silos beyond maximum

#### AI Output Governance (`app/governance/ai_output.py`)
**Pre-Generation:**
- Silo structure validation
- Initial cannibalization check (if embedding available)
- Content structure validation (title, slug)

**During Generation:**
- Output length constraints (500-50,000 chars)
- Sentence structure validation (minimum 5 sentences)
- Intent preservation (keyword presence check)

**Post-Generation:**
- Final cannibalization check with actual embedding
- Authority preservation validation
- Content completeness check
- **Week 5 Enhancements:**
  - Entity coverage validation (minimum 3 entities)
  - FAQ minimum validation (minimum 3 FAQs with question + answer)
  - Link validation (no hallucinated links)
  - FAQ schema enforcement

#### Publishing Safety (`app/governance/publishing.py`)
- All governance checks must pass
- Embedding must exist
- Authority sources required for high-authority content
- Content structure validation
- Status validation (blocks BLOCKED/DECOMMISSIONED content)

**Authority Preservation:**
- Preserves authority score on decommission
- Maintains source URLs
- Stores redirect information
- Creates audit trail

#### Lifecycle Gates (`app/governance/lifecycle_gates.py`) - Week 6
- **6 Gates** that must all pass before publishing:
  1. Governance checks gate - All governance checks (pre/during/post) must have passed
  2. Schema sync validation gate - JSON-LD schema must match content (title, path, dates)
  3. Embedding gate - Vector embedding must exist for cannibalization tracking
  4. Authority gate - High authority content requires source URLs
  5. Content structure gate - Title, body, and path must be valid
  6. Status gate - Status must allow publishing (APPROVED or DRAFT, not BLOCKED/DECOMMISSIONED)
- Blocks publishing if any gate fails
- Returns detailed error codes for failed gates

#### Redirect Manager (`app/governance/redirect_manager.py`) - Week 6
- Validates redirect URLs (internal paths or external URLs)
- Verifies internal redirect targets exist and are published
- Enforces redirects on decommission
- Stores redirect metadata in governance_checks
- Logs all redirect enforcement actions

### 3. Queue System (Redis-based)

**Queue Manager** (`app/queues/queue_manager.py`)
- Redis-based job queue (BullMQ-compatible pattern)
- Asynchronous job processing
- Job status tracking
- Retry logic support
- **Week 5: Bulk job processing** - Process multiple jobs in batch

**Job Processor** (`app/queues/job_processor.py`)
- Orchestrates full generation pipeline
- Integrates all governance stages
- OpenAI API integration with structured outputs (Week 5)
- Retry logic with cost tracking (Week 5)
- Automatic retry on failures (up to max_retries)
- Cost limit enforcement per job
- Embedding generation
- JSON-LD schema generation

**Structured Output Generator** (`app/governance/structured_output.py`) - Week 5
- Enforces structured output schema (body, entities, FAQs, links)
- Uses OpenAI structured outputs API with fallback
- Validates output structure before returning
- Prevents hallucinated links and ensures FAQ schema compliance

**Cost Calculator** (`app/governance/cost_calculator.py`) - Week 5
- Tracks costs for all AI API calls
- Supports GPT-4, GPT-3.5, and embedding models
- Enforces cost limits per job

### 4. JSON-LD Schema Generation

**Hybrid Generation** (`app/schemas/jsonld.py`)
- **Backend-driven, not AI-generated**
- Ensures structure and consistency
- Generates:
  - Article schema
  - Breadcrumb structure (Reverse Silos)
  - Organization schema
  - Source citations
  - Aggregate ratings (for high authority)

### 5. API Layer (FastAPI)

**Route Organization:**
- `app/api/routes/sites.py` - Site management
- `app/api/routes/pages.py` - Page lifecycle and publishing
- `app/api/routes/jobs.py` - Job management
- `app/api/routes/silos.py` - Silo management

**Dependency Injection:**
- `app/api/dependencies.py` - Service dependency functions
- All routes use FastAPI's `Depends()` for testability

**Exception Handling:**
- `app/api/exception_handlers.py` - Custom exception handlers
- Consistent error response format with error codes
- Handles governance errors, validation errors, and database errors

**Endpoints:**
- Site management
- Silo management (with structure enforcement)
- Content creation and generation
- Publishing (with lifecycle gates - Week 6)
- Decommissioning (with authority preservation and redirect enforcement - Week 6)
- Job status tracking
- JSON-LD schema retrieval
- Gate checking (check gates without publishing - Week 6)

## Data Flow

### Content Generation Flow

```
1. Create Content Request
   ↓
2. Pre-Generation Governance
   - Silo structure check
   - Initial cannibalization check
   - Structure validation
   ↓
3. Queue Generation Job
   ↓
4. During Generation
   - AI content generation
   - Output quality checks
   - Intent preservation
   ↓
5. Post-Generation Governance
   - Final cannibalization check
   - Authority validation
   - Completeness check
   ↓
6. JSON-LD Schema Generation
   ↓
7. Publishing Safety Check
   ↓
8. Content Status: APPROVED or BLOCKED
```

### Publishing Flow (Week 6)

```
1. Publish Request
   ↓
2. Lifecycle Gate Check (6 gates)
   - Gate 1: Governance checks (pre/during/post)
   - Gate 2: Schema sync validation
   - Gate 3: Embedding exists
   - Gate 4: Authority validation
   - Gate 5: Content structure
   - Gate 6: Status allows publishing
   ↓
3. If All Gates Pass: Status → PUBLISHED
   If Any Gate Fails: Raise LifecycleGateError with error code
```

### Decommissioning Flow (Week 6)

```
1. Decommission Request (with optional redirect)
   ↓
2. Redirect Validation
   - Validate redirect URL format
   - Verify internal target exists (if internal)
   - Check target is published (if internal)
   ↓
3. Preserve Authority
   - Store authority score
   - Maintain source URLs
   - Enforce redirect (if provided)
   - Store redirect metadata in governance_checks
   - Create audit log
   ↓
4. Status → DECOMMISSIONED
```

## Governance Enforcement Points

1. **Silo Creation** - Enforces 3-7 limit
2. **Content Creation** - Pre-generation checks
3. **AI Generation** - During-generation monitoring
4. **Post-Generation** - Final validation
5. **Publishing** - 6 lifecycle gates (Week 6)
6. **Decommissioning** - Authority preservation with redirect enforcement (Week 6)

## Technology Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 14+ with pgvector
- **Queue**: Redis 6+ (BullMQ-compatible pattern)
- **AI**: OpenAI API (GPT-4, text-embedding-3-small)
- **Schema**: JSON-LD (backend-generated)

## Key Design Decisions

1. **Backend-driven JSON-LD**: Ensures consistency and structure
2. **Three-stage governance**: Pre, during, and post-generation checks
3. **Vector embeddings**: Semantic similarity for cannibalization detection
4. **Hard silo limits**: Structural enforcement at database level
5. **Comprehensive audit trail**: All governance actions logged via SystemEvent
6. **Authority preservation**: Never lose source credibility data
7. **Page model (not Content)**: Refactored for consistency - pages have governance_checks JSONB column
8. **Structured outputs (Week 5)**: AI writes only what's allowed by schema
9. **Retry-cost safety (Week 5)**: Automatic retries with cost tracking and limits
10. **Enhanced postcheck (Week 5)**: Entity coverage, FAQ minimum, link validation
11. **Lifecycle gates (Week 6)**: 6 gates must all pass before publishing - unsafe content cannot ship
12. **Redirect enforcement (Week 6)**: Validates and enforces redirects on decommission
13. **Type safety**: Complete type hints with TypedDict classes for all complex return types
14. **Error handling**: Custom exceptions with error codes and consistent response format
15. **Dependency injection**: All services use FastAPI DI for testability
16. **Route organization**: Routes split by domain (sites, pages, jobs, silos)
17. **Service layer**: Business logic separated from HTTP concerns
18. **Centralized configuration**: All hard-coded values moved to settings

## Scalability Considerations

- Async/await throughout for I/O operations
- Redis queue for horizontal scaling
- Database connection pooling
- Vector index optimization for similarity searches
- Job concurrency control (5 concurrent jobs default)

## Security Considerations

- Environment-based configuration
- Secret key management
- Input validation at API layer
- SQL injection prevention (SQLAlchemy ORM)
- CORS configuration for production

