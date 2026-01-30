# WordPress Plugin Integration Guide

Complete guide to connecting your WordPress site with the Siloq backend API.

## Overview

The Siloq WordPress plugin communicates with the Siloq backend via REST API using API key authentication. This guide covers the complete setup process.

## Changes Made

### 1. Backend Changes

#### ✅ API Key Authentication System
- **Added** `APIKey` model (`app/db/models.py:702-739`)
- **Added** API key database migration (`migrations/V013__api_keys_table.sql`)
- **Updated** authentication to support both JWT and API keys (`app/core/auth.py`)
- **Added** API key management endpoints (`app/api/routes/api_keys.py`)

#### ✅ API Key Features
- Secure SHA-256 hashing for storage
- Scoped permissions (read, write, admin)
- Usage tracking (last_used_at, usage_count)
- Optional expiration dates
- Revocation support with audit trail
- API keys prefixed with `sk-` for identification

#### ✅ WordPress-Specific Endpoints
All required endpoints are available:
- `GET /api/v1/sites/{site_id}` - Test connection
- `POST /api/v1/pages` - Create page
- `GET /api/v1/pages/{page_id}` - Get page
- `PUT /api/v1/pages/{page_id}` - Update page
- `POST /api/v1/pages/{page_id}/validate` - Validate page ✅ **Already existed**
- `POST /api/v1/pages/{page_id}/publish` - Publish page with gates
- `GET /api/v1/pages/{page_id}/jsonld` - Get JSON-LD schema
- `GET /api/v1/pages/{page_id}/gates` - Check lifecycle gates
- `GET /api/v1/jobs/{job_id}` - Get job status
- `POST /api/v1/jobs/{job_id}/transition` - Transition job state

## Setup Instructions

### Step 1: Run Database Migration

Apply the API keys migration to your database:

```bash
# Navigate to project directory
cd /Users/jumar.juaton/Documents/GitHub/siloq

# Apply migration (using PostgreSQL)
psql $DATABASE_URL -f migrations/V013__api_keys_table.sql
```

Or if using the connection string from .env:

```bash
psql "postgresql://doadmin:YOUR_PASSWORD@private-db-siloq-postgres-do-user-31099676-0.k.db.ondigitalocean.com:25060/defaultdb?sslmode=require" -f migrations/V013__api_keys_table.sql
```

### Step 2: Start the Siloq Backend

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **Local**: `http://localhost:8000/api/v1`
- **Health check**: `http://localhost:8000/health`

**Local CORS:** In development, the API allows these origins by default so the dashboard and WordPress can call it from the browser:
- `http://localhost:3000`, `http://127.0.0.1:3000` (siloq-dashboard)
- `http://localhost:8080`, `http://127.0.0.1:8080` (WordPress)
- `http://localhost:8081`, `http://127.0.0.1:8081`

To add more origins, set in `siloq-app/.env`: `CORS_ORIGINS=http://localhost:3000,http://localhost:8080`

### Step 3: Create a Site

First, create a site in Siloq (you'll need authentication - for now we can skip auth for this step):

```bash
curl -X POST http://localhost:8000/api/v1/sites \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My WordPress Site",
    "domain": "example.com"
  }'
```

**Note:** For now, temporarily comment out the `current_user: dict = Depends(get_current_user)` line in `app/api/routes/sites.py` to create sites without auth, or generate a JWT token.

Save the `id` (UUID) from the response - this is your **Site ID**.

Example response:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "My WordPress Site",
  "domain": "example.com",
  "created_at": "2026-01-17T10:00:00Z"
}
```

### Step 4: Generate an API Key

Create an API key for the WordPress plugin:

```bash
curl -X POST http://localhost:8000/api/v1/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "WordPress Plugin",
    "scopes": ["read", "write"],
    "expires_in_days": null
  }'
```

**Important:** The API key is only returned once! Save it securely.

Example response:
```json
{
  "id": "987fcdeb-51a2-43f7-8b4a-123456789abc",
  "site_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "WordPress Plugin",
  "key_prefix": "sk-a1b2c",
  "scopes": ["read", "write"],
  "is_active": true,
  "created_at": "2026-01-17T10:05:00Z",
  "expires_at": null,
  "last_used_at": null,
  "usage_count": 0,
  "api_key": "sk-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"
}
```

Copy the `api_key` value (starts with `sk-`).

### Step 5: Install WordPress Plugin

1. Copy the plugin to WordPress:
```bash
cp -r wordpress-plugin /path/to/wordpress/wp-content/plugins/siloq-connector
```

2. Activate the plugin in WordPress:
   - Go to **Plugins** → **Installed Plugins**
   - Find **Siloq Connector**
   - Click **Activate**

### Step 6: Configure WordPress Plugin

1. In WordPress admin, go to **Settings** → **Siloq**

2. Enter the configuration:

| Setting | Value | Example |
|---------|-------|---------|
| **API Base URL** | Your backend URL + `/api/v1` | `http://localhost:8000/api/v1` |
| **API Key** | The `sk-` key from Step 4 | `sk-a1b2c3d4e5f6...` |
| **Site ID** | The UUID from Step 3 | `123e4567-e89b-12d3-a456-426614174000` |

3. Click **Save Settings**

4. Click **Test API Connection**

You should see: ✅ "Connection successful! Site: My WordPress Site"

### Step 7: Test the Integration

#### Test 1: Manual Sync

1. Create a test page in WordPress
2. Go to **Settings** → **Siloq**
3. Click **Sync All Pages to Siloq**
4. Check the sync results

#### Test 2: Auto Sync

1. Enable **Auto Sync on Publish** in settings
2. Create or update a WordPress page
3. Publish it
4. The page should automatically sync to Siloq

#### Test 3: Check API Key Usage

```bash
curl -X GET "http://localhost:8000/api/v1/api-keys/site/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer sk-your-api-key-here"
```

You should see the `usage_count` increase and `last_used_at` updated.

## API Key Management

### List All Keys for a Site

```bash
curl -X GET "http://localhost:8000/api/v1/api-keys/site/{site_id}" \
  -H "Authorization: Bearer sk-your-api-key-here"
```

### Revoke an API Key

```bash
curl -X DELETE "http://localhost:8000/api/v1/api-keys/{key_id}?reason=Compromised" \
  -H "Authorization: Bearer sk-your-api-key-here"
```

### Get API Key Details

```bash
curl -X GET "http://localhost:8000/api/v1/api-keys/{key_id}" \
  -H "Authorization: Bearer sk-your-api-key-here"
```

## Authentication Flow

The system supports two authentication methods:

### 1. API Key Authentication (WordPress Plugin)
- WordPress plugin sends: `Authorization: Bearer sk-xxxxx...`
- Backend validates API key and returns site context
- All requests are scoped to the associated site

### 2. JWT Authentication (Web Dashboard)
- User logs in and receives JWT token
- Token includes `user_id` and `account_id`
- Multi-site access based on account ownership

## Troubleshooting

### Connection Test Fails

**Error: "Invalid API key"**
- Verify the API key is correct and starts with `sk-`
- Check the key is active: `is_active = true`
- Check expiration: `expires_at` should be null or future date

**Error: "Site not found"**
- Verify the Site ID (UUID) is correct
- Ensure the site exists in the database

**Error: "Could not connect to server" / "Failed to connect to localhost port 8000"**
- Check the API Base URL is correct
- Ensure the Siloq backend is running (e.g. `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`)
- **WordPress in Docker**: If WordPress runs inside a container, `localhost` inside the container is the container itself, not your host. Use:
  - **Docker Desktop (Windows/Mac)**: `http://host.docker.internal:8000/api/v1`
  - **Linux**: Use your host IP (e.g. `http://172.17.0.1:8000/api/v1`) or run WordPress and the API on the same network
- Check firewall/network settings
- Try the health endpoint from the machine running WordPress: `http://<api-host>:8000/health`

### Pages Not Syncing

**Check 1: Auto Sync Enabled**
- Go to Settings → Siloq
- Verify "Auto Sync on Publish" is checked
- Verify "Enable Sync" is checked

**Check 2: Post Type Included**
- Check "Post Types to Sync" includes your post type
- Default: `page` and `post`

**Check 3: WordPress Logs**
- Enable `WP_DEBUG` in `wp-config.php`
- Check error logs for API errors

**Check 4: Backend Logs**
- Check FastAPI server logs for incoming requests
- Look for authentication or validation errors

### API Key Not Working

**Check API Key in Database:**
```sql
SELECT
  id,
  site_id,
  name,
  key_prefix,
  is_active,
  expires_at,
  last_used_at,
  usage_count
FROM api_keys
WHERE key_prefix = 'sk-a1b2c';
```

**Common Issues:**
- Key was revoked: `is_active = false`
- Key expired: `expires_at < NOW()`
- Key hash doesn't match (key was re-created)

## Security Best Practices

### For Production:

1. **Use HTTPS for API Base URL**
   ```
   https://api.yourdomain.com/api/v1
   ```

2. **Set API Key Expiration**
   ```json
   {
     "expires_in_days": 365
   }
   ```

3. **Use Scoped Permissions**
   ```json
   {
     "scopes": ["read"]  // Read-only for monitoring
   }
   ```

4. **Rotate Keys Regularly**
   - Create new key
   - Update WordPress settings
   - Revoke old key

5. **Monitor Usage**
   - Check `usage_count` for anomalies
   - Review `last_used_at` for suspicious activity

6. **Revoke Compromised Keys Immediately**
   ```bash
   curl -X DELETE "http://localhost:8000/api/v1/api-keys/{key_id}?reason=Compromised"
   ```

## Next Steps

Once the integration is working:

1. **Configure Silos** in Siloq backend
2. **Set up content generation** rules
3. **Configure lifecycle gates** for publishing
4. **Enable webhooks** for bidirectional sync
5. **Test JSON-LD schema** injection
6. **Configure redirect management**

## API Endpoints Reference

### Sites
- `POST /api/v1/sites` - Create site
- `GET /api/v1/sites/{site_id}` - Get site

### Pages
- `POST /api/v1/pages` - Create page
- `GET /api/v1/pages/{page_id}` - Get page
- `PUT /api/v1/pages/{page_id}` - Update page
- `POST /api/v1/pages/{page_id}/validate` - Validate before generation
- `POST /api/v1/pages/{page_id}/publish` - Publish with gates
- `GET /api/v1/pages/{page_id}/jsonld` - Get JSON-LD schema
- `GET /api/v1/pages/{page_id}/gates` - Check all gates
- `POST /api/v1/pages/{page_id}/decommission` - Decommission page

### Jobs
- `GET /api/v1/jobs/{job_id}` - Get job status
- `POST /api/v1/jobs/{job_id}/transition` - Transition state

### API Keys
- `POST /api/v1/api-keys` - Create new key
- `GET /api/v1/api-keys/site/{site_id}` - List keys for site
- `GET /api/v1/api-keys/{key_id}` - Get key details
- `DELETE /api/v1/api-keys/{key_id}` - Revoke key

### WordPress (TALI)
- `POST /api/v1/wordpress/projects/{project_id}/theme-profile` - Sync theme
- `GET /api/v1/wordpress/claims/{claim_id}/state` - Check claim state
- `POST /api/v1/wordpress/projects/{project_id}/pages/sync` - Sync page

## Support

For issues or questions:
1. Check the **Troubleshooting** section above
2. Review WordPress error logs: `wp-content/debug.log`
3. Review backend logs: FastAPI console output
4. Check API connectivity: Test `/health` endpoint
