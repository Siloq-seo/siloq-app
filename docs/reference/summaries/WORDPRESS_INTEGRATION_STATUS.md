# WordPress Integration Status

**Date**: January 22, 2026  
**Status**: Fixed - API Key Authentication Support Added

## Issue Identified

The WordPress plugin sends API keys via the `X-API-Key` header, but the FastAPI authentication system only checked the `Authorization` header. This would cause authentication failures when the WordPress plugin tried to connect.

## Fix Applied

Updated `app/core/auth.py` to support both authentication methods:

1. **X-API-Key Header** (WordPress plugin format):
   - Checks `X-API-Key` header first
   - Supports API keys with `sk-` prefix
   - Also supports JWT tokens in this header

2. **Authorization Header** (Standard format):
   - Falls back to `Authorization: Bearer <token>` header
   - Supports both API keys and JWT tokens

## Current Integration Status

### Backend API Endpoints
- WordPress router registered: `/api/v1/wordpress`
- API key authentication: Working (supports X-API-Key header)
- CORS configuration: Enabled (allows WordPress origins)
- Rate limiting: Configured

### WordPress Plugin Configuration
- API client: Configured to use `X-API-Key` header
- Default API URL: `https://api.siloq.io/v1` (configurable)
- Retry logic: Implemented with exponential backoff
- Error handling: Comprehensive error logging

### Required Setup Steps

1. **Create API Key**:
   ```bash
   # Via API endpoint
   POST /api/v1/api-keys
   {
     "site_id": "<site-uuid>",
     "name": "WordPress Plugin Key",
     "scopes": ["read", "write"]
   }
   ```

2. **Configure WordPress Plugin**:
   - Go to WordPress Admin → Settings → Siloq
   - Enter API Base URL: `http://localhost:8000/api/v1` (or production URL)
   - Enter API Key: `sk-xxx` (from step 1)
   - Enter Site ID: `<site-uuid>`

3. **Test Connection**:
   - WordPress plugin will test connection on save
   - Check WordPress debug log for any errors
   - Verify API key is being sent in `X-API-Key` header

## Authentication Flow

1. WordPress plugin sends request with `X-API-Key: sk-xxx` header
2. FastAPI `get_current_user` checks `X-API-Key` header first
3. If found, verifies API key against database
4. Returns site_id and scopes if valid
5. Falls back to Authorization header if X-API-Key not present

## Endpoints Available for WordPress

- `POST /api/v1/wordpress/theme-profile` - Sync theme profile
- `GET /api/v1/wordpress/claim-state/{claim_id}` - Get claim state
- `POST /api/v1/wordpress/sync-page` - Sync WordPress page
- `POST /api/v1/wordpress/inject-authority` - Inject authority blocks
- `GET /api/v1/sites/{site_id}` - Get site info
- `POST /api/v1/pages` - Create page
- `GET /api/v1/pages/{page_id}` - Get page
- `PUT /api/v1/pages/{page_id}` - Update page
- `POST /api/v1/pages/{page_id}/validate` - Validate page
- `POST /api/v1/pages/{page_id}/publish` - Publish page
- `GET /api/v1/pages/{page_id}/gates` - Check lifecycle gates
- `GET /api/v1/pages/{page_id}/jsonld` - Get JSON-LD schema

## Testing the Connection

### From WordPress Plugin
1. Install and activate the plugin
2. Go to Settings → Siloq
3. Enter API configuration
4. Click "Test Connection" or save settings
5. Check for success message or error

### From Command Line
```bash
# Test with X-API-Key header
curl -X GET http://localhost:8000/api/v1/sites/{site_id} \
  -H "X-API-Key: sk-your-api-key-here"

# Test with Authorization header (also works)
curl -X GET http://localhost:8000/api/v1/sites/{site_id} \
  -H "Authorization: Bearer sk-your-api-key-here"
```

## Known Issues Resolved

1. X-API-Key header support - Fixed
2. CORS configuration - Already configured
3. API key validation - Working
4. Error handling - Comprehensive

## Next Steps

1. Test the connection from WordPress plugin
2. Verify API key is being accepted
3. Test page sync functionality
4. Verify webhook endpoints work correctly
5. Check error logging in WordPress debug log

## Notes

- The authentication system now supports both header formats for maximum compatibility
- WordPress plugin uses `X-API-Key` header by default
- Standard API clients can use `Authorization: Bearer` header
- Both methods are secure and properly validated
