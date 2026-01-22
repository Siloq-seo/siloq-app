# Pydantic V2 Compatibility Fix

## Issue

Pydantic V2 warning:
```
UserWarning: Valid config keys have changed in V2:
* 'schema_extra' has been renamed to 'json_schema_extra'
```

## Fix Applied

Updated all instances of `schema_extra` to `json_schema_extra` in Pydantic model Config classes.

## Files Modified

### `app/decision/schemas.py`

Replaced `schema_extra` with `json_schema_extra` in 4 Config classes:

1. **ValidationPayload.Config** (line 70)
   - Changed `schema_extra` → `json_schema_extra`

2. **ValidationResult.Config** (line 121)
   - Changed `schema_extra` → `json_schema_extra`

3. **StateTransitionRequest.Config** (line 159)
   - Changed `schema_extra` → `json_schema_extra`

4. **StateTransitionResponse.Config** (line 189)
   - Changed `schema_extra` → `json_schema_extra`

## Verification

- ✅ All instances of `schema_extra` replaced with `json_schema_extra`
- ✅ No remaining `schema_extra` in codebase
- ✅ Import test passed: `from app.decision.schemas import ValidationPayload` works correctly
- ✅ Pydantic V2 compatible

## Impact

This fix eliminates the Pydantic V2 warning that appears during application startup. The functionality remains the same - only the configuration key name was updated to match Pydantic V2 requirements.

## Pydantic V2 Changes

In Pydantic V2, the `Config` class attribute `schema_extra` was renamed to `json_schema_extra` to be more explicit about its purpose (modifying the JSON schema).

**Before (Pydantic V1):**
```python
class Config:
    schema_extra = {"example": {...}}
```

**After (Pydantic V2):**
```python
class Config:
    json_schema_extra = {"example": {...}}
```
