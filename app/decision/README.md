# Decision Engine - Week 2

## Overview

The Decision Engine is a governance-first validation system that ensures no content generation proceeds without proper validation and state management.

## Architecture

### Components

1. **Error Code Dictionary v1.4** (`error_codes.py`)
   - Standardized error codes with doctrine references
   - 20+ error codes across 4 categories
   - Each error includes remediation steps

2. **Preflight Validator** (`preflight_validator.py`)
   - Validates all conditions before generation
   - Returns actionable error codes
   - Integrates with existing governance checks

3. **State Machine** (`state_machine.py`)
   - Type-safe state management
   - Transition guards prevent invalid changes
   - Sequential state enforcement

4. **Validation Schemas** (`schemas.py`)
   - Strict input/output contracts
   - Pydantic validation
   - Type-safe payloads

5. **Event Logger** (`event_logger.py`)
   - Comprehensive audit trail
   - Logs all validations and state changes
   - Queryable history

## State Machine

### Valid States

- `DRAFT` - Initial state
- `PREFLIGHT_APPROVED` - Preflight validation passed
- `PROMPT_LOCKED` - Prompt locked for generation
- `PROCESSING` - Content generation in progress
- `POSTCHECK_PASSED` - Post-generation checks passed
- `POSTCHECK_FAILED` - Post-generation checks failed
- `COMPLETED` - Job completed successfully
- `FAILED` - Job failed
- `AI_MAX_RETRY_EXCEEDED` - Week 5: Maximum retries exceeded
- `LIFECYCLE_GATES_FAILED` - Week 6: One or more lifecycle gates failed (implicit state)

### State Transitions

```
DRAFT
  ↓
PREFLIGHT_APPROVED (after validation)
  ↓
PROMPT_LOCKED (prompt locked)
  ↓
PROCESSING (generation started)
  ↓
POSTCHECK_PASSED / POSTCHECK_FAILED
  ↓
COMPLETED / FAILED
```

### Transition Rules

- States cannot be skipped
- Transitions must follow valid paths
- Locked states prevent modifications
- All transitions are logged

## Error Codes

### Categories

- **PREFLIGHT_*** - Preflight validation errors
- **STATE_*** - State machine errors
- **POSTCHECK_*** - Post-generation check errors (includes Week 5: entity coverage, FAQ minimum, link validation)
- **AI_*** - Week 5: AI generation errors (retry exceeded, cost limit exceeded)
- **LIFECYCLE_*** - Week 6: Lifecycle gate errors (governance, schema sync, embedding, authority, structure, status, redirect)
- **SYSTEM_*** - System errors

### Error Format

Each error includes:
- `code` - Error code (e.g., `PREFLIGHT_001`)
- `message` - Human-readable message
- `doctrine_reference` - Policy/rule reference
- `remediation_steps` - Steps to fix the issue
- `severity` - Error severity level

## API Usage

### Validate Page

```python
POST /pages/{page_id}/validate
Content-Type: application/json

{
    "page_id": "uuid",
    "site_id": "uuid",
    "path": "/example",
    "title": "Example Title",
    "silo_id": "uuid",
    "keyword": "example-keyword"
}
```

### Transition State

```python
POST /jobs/{job_id}/transition
Content-Type: application/json

{
    "target_state": "preflight_approved",
    "reason": "Validation passed",
    "error_code": null
}
```

### Get History

```python
GET /pages/{page_id}/validation-history?limit=10
GET /jobs/{job_id}/state-history?limit=20
```

## Integration

The Decision Engine integrates with:
- Existing governance checks (cannibalization, silos)
- State machine for job management
- Event logging for audit trail
- API endpoints for validation

## Testing

All components include:
- Type safety
- Error handling
- State validation
- Audit logging

## Doctrine References

Each error references a doctrine policy:
- `DOCTRINE-STRUCTURE-*` - Structural rules
- `DOCTRINE-CONTENT-*` - Content rules (includes Week 5: entity coverage, FAQ schema, link validation)
- `DOCTRINE-CANNIBALIZATION-*` - Cannibalization rules
- `DOCTRINE-STATE-*` - State machine rules
- `DOCTRINE-AUTHORITY-*` - Authority rules
- `DOCTRINE-AI-*` - Week 5: AI generation rules (retry limits, cost limits)
- `DOCTRINE-PUBLISH-*` - Week 6: Publishing rules (lifecycle gates)
- `DOCTRINE-DECOMMISSION-*` - Week 6: Decommission rules (redirect validation)
- `DOCTRINE-SYSTEM-*` - System rules

## Week 5 Enhancements

The Decision Engine now includes enhanced postcheck validation:
- **Entity Coverage** (POSTCHECK_007): Minimum 3 entities required
- **FAQ Minimum** (POSTCHECK_008): Minimum 3 FAQs required
- **FAQ Schema** (POSTCHECK_010): Each FAQ must have question and answer
- **Link Validation** (POSTCHECK_009): No hallucinated links allowed
- **Retry Safety** (AI_MAX_RETRY_EXCEEDED): Maximum retries exceeded
- **Cost Safety** (AI_COST_LIMIT_EXCEEDED): Cost limit exceeded per job

## Week 6 Enhancements

The Decision Engine now includes lifecycle gate error codes:
- **LIFECYCLE_001**: Governance checks gate failed
- **LIFECYCLE_002**: Schema sync validation failed
- **LIFECYCLE_003**: Embedding gate failed
- **LIFECYCLE_004**: Authority gate failed
- **LIFECYCLE_005**: Content structure gate failed
- **LIFECYCLE_006**: Status gate failed
- **LIFECYCLE_007**: Invalid redirect URL for decommission

All lifecycle gate errors include detailed remediation steps and reference the appropriate doctrine policy.

