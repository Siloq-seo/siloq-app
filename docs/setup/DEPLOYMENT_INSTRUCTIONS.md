# WordPress Integration - Deployment Instructions

## Overview
This guide will help you deploy the WordPress plugin and connect it to your Siloq backend API.

## Prerequisites
- ✅ WordPress site (version 5.8+)
- ✅ PHP 7.4+ on WordPress server
- ✅ Siloq backend API deployed and accessible
- ✅ Database access to run migration

## Step 1: Deploy Database Migration

Run the API keys migration on your production database:

```bash
# Connect to your database server or use a tool like TablePlus/pgAdmin
psql "postgresql://doadmin:YOUR_PASSWORD@private-db-siloq-postgres-do-user-31099676-0.k.db.ondigitalocean.com:25060/defaultdb?sslmode=require" -f migrations/V013__api_keys_table.sql
```

Or copy the SQL and run it manually:
```sql
-- Create api_keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    key_prefix VARCHAR(10) NOT NULL,
    name VARCHAR NOT NULL,
    scopes JSONB NOT NULL DEFAULT '["read", "write"]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_reason TEXT,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT chk_api_key_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_key_hash_length CHECK (length(trim(key_hash)) = 64),
    CONSTRAINT chk_key_prefix_length CHECK (length(trim(key_prefix)) >= 8),
    CONSTRAINT chk_usage_count_non_negative CHECK (usage_count >= 0)
);

CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_site_id ON api_keys(site_id);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
```

## Step 2: Install WordPress Plugin

### Option A: Upload via WordPress Admin (Easiest)
1. Zip the plugin folder:
   ```bash
   cd /Users/jumar.juaton/Documents/Github/siloq
   zip -r siloq-connector.zip wordpress-plugin/
   ```

2. In WordPress admin:
   - Go to **Plugins** → **Add New** → **Upload Plugin**
   - Upload `siloq-connector.zip`
   - Click **Install Now**
   - Click **Activate**

### Option B: Upload via FTP/SSH
1. Upload the `wordpress-plugin/` folder to your WordPress server:
   ```bash
   # Via SCP (adjust paths and server address)
   scp -r wordpress-plugin/ user@yourserver.com:/path/to/wordpress/wp-content/plugins/siloq-connector/
   ```

2. Activate in WordPress:
   - Go to **Plugins** → **Installed Plugins**
   - Find **Siloq Connector**
   - Click **Activate**

## Step 3: Create a Site and API Key

You have two options:

### Option A: Via Backend API (If accessible)

1. **Create a Site:**
```bash
curl -X POST https://your-api-domain.com/api/v1/sites \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My WordPress Site",
    "domain": "yoursite.com"
  }'
```

Save the `id` from the response (this is your SITE_ID).

2. **Generate API Key:**
```bash
curl -X POST https://your-api-domain.com/api/v1/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "YOUR_SITE_ID_HERE",
    "name": "WordPress Plugin Key",
    "scopes": ["read", "write"],
    "expires_in_days": null
  }'
```

**IMPORTANT:** Copy the `api_key` value - it starts with `sk-` and will only be shown once!

### Option B: Via Database (If API not accessible yet)

1. **Create a Site** (insert directly into database):
```sql
INSERT INTO sites (id, name, domain, created_at)
VALUES (
    gen_random_uuid(),
    'My WordPress Site',
    'yoursite.com',
    NOW()
)
RETURNING id;
```

Save the returned `id`.

2. **Generate API Key** (use Python script):
```python
import hashlib
import secrets

# Generate API key
api_key = f"sk-{secrets.token_bytes(32).hex()}"
print(f"API Key (save this!): {api_key}")

# Generate hash for storage
key_hash = hashlib.sha256(api_key.encode()).hexdigest()
key_prefix = api_key[:8]

print(f"Key Hash: {key_hash}")
print(f"Key Prefix: {key_prefix}")
```

Then insert into database:
```sql
INSERT INTO api_keys (site_id, key_hash, key_prefix, name, scopes)
VALUES (
    'YOUR_SITE_ID_HERE',  -- from step 1
    'KEY_HASH_FROM_PYTHON',
    'KEY_PREFIX_FROM_PYTHON',
    'WordPress Plugin Key',
    '["read", "write"]'::jsonb
);
```

## Step 4: Configure WordPress Plugin

1. In WordPress admin, go to **Settings** → **Siloq**

2. Enter your configuration:
   - **API Base URL**: `https://your-api-domain.com/api/v1`
   - **API Key**: The `sk-...` key from Step 3
   - **Site ID**: The UUID from Step 3

3. Click **Save Settings**

4. Click **Test API Connection**
   - You should see: ✅ "Connection successful!"

## Step 5: Test the Integration

### Test 1: Manual Page Sync
1. Create a test page in WordPress
2. Go to **Settings** → **Siloq**
3. Click **Sync All Pages to Siloq**
4. Verify the page was synced

### Test 2: Auto Sync
1. Enable **Auto Sync on Publish** in settings
2. Create a new WordPress page
3. Publish it
4. Verify it auto-syncs to Siloq

## Troubleshooting

### Connection Test Fails

**Error: "Invalid API key"**
- Verify the API key is correct (starts with `sk-`)
- Check the key is active in database: `SELECT * FROM api_keys WHERE key_prefix = 'sk-xxxxx'`

**Error: "Site not found"**
- Verify the Site ID is correct UUID format
- Check site exists: `SELECT * FROM sites WHERE id = 'YOUR_SITE_ID'`

**Error: "Could not connect"**
- Verify the API Base URL is correct and accessible
- Check SSL certificate if using HTTPS
- Test with curl: `curl https://your-api-domain.com/api/v1/health`

### Pages Not Syncing

1. Check WordPress error log: `wp-content/debug.log`
2. Enable `WP_DEBUG` in `wp-config.php`:
   ```php
   define('WP_DEBUG', true);
   define('WP_DEBUG_LOG', true);
   ```
3. Verify API key has `write` scope
4. Check backend API logs for errors

## API Endpoints Reference

Base URL: `https://your-api-domain.com/api/v1`

### Health Check
```bash
GET /health
```

### Sites
```bash
POST /sites
GET /sites/{site_id}
```

### Pages
```bash
POST /pages
GET /pages/{page_id}
PUT /pages/{page_id}
POST /pages/{page_id}/validate
POST /pages/{page_id}/publish
```

### API Keys
```bash
POST /api-keys
GET /api-keys/site/{site_id}
DELETE /api-keys/{key_id}
```

## Security Recommendations

1. **Use HTTPS** for all API connections
2. **Rotate API keys** regularly (create new, update WordPress, revoke old)
3. **Set key expiration** for enhanced security:
   ```json
   {"expires_in_days": 365}
   ```
4. **Monitor usage**:
   ```sql
   SELECT name, last_used_at, usage_count
   FROM api_keys
   WHERE site_id = 'YOUR_SITE_ID';
   ```
5. **Revoke compromised keys immediately**:
   ```bash
   curl -X DELETE https://your-api/api/v1/api-keys/{key_id}?reason=Compromised
   ```

## Next Steps

Once the plugin is connected:
1. Configure content silos in Siloq backend
2. Set up lifecycle gates
3. Enable JSON-LD schema injection
4. Configure redirect management
5. Test TALI (Theme-Aware Layout Intelligence) features

## Support

- Documentation: `/WORDPRESS_INTEGRATION_GUIDE.md`
- API Endpoints: `/WORDPRESS_INTEGRATION_GUIDE.md#api-endpoints-reference`
- Backend API: Check health at `https://your-api/health`
