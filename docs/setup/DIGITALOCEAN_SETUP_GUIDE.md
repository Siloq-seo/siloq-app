# Complete Setup Guide: Siloq on DigitalOcean App Platform

This guide walks you through setting up your Siloq deployment on DigitalOcean App Platform and connecting it to WordPress.

## Prerequisites

- ✅ DigitalOcean App Platform app created (siloq-app)
- ✅ WordPress site ready to connect
- ✅ Access to DigitalOcean dashboard

---

## Part 1: Get Your SECRET_KEY from DigitalOcean

### Step 1: Access Your App Settings

1. Go to https://cloud.digitalocean.com/
2. Click **Apps** in the left sidebar
3. Click on your **siloq-app** (or whatever you named it)
4. Click **Settings** tab at the top

### Step 2: Find Environment Variables

1. Scroll down to **App-Level Environment Variables** section
2. Look for `SECRET_KEY` in the list
3. Click on the value to reveal it (or click the eye icon)
4. **Copy the entire SECRET_KEY value**

**Alternative:** If `SECRET_KEY` doesn't exist, you may need to:
- Check **Component-Level Environment Variables** (if you have multiple components)
- Or add it manually (see Part 2)

### Step 3: Verify Your API URL

While you're in Settings, note your app's URL:
- Your app URL should be: `https://siloq-app-edwlr.ondigitalocean.app`
- API base URL: `https://siloq-app-edwlr.ondigitalocean.app/api/v1`

---

## Part 2: Generate a JWT Token (For Initial Setup)

### Step 1: Get SECRET_KEY Locally

```bash
# Navigate to your local project
cd /Users/jumar.juaton/Documents/GitHub/siloq

# Export the SECRET_KEY you copied from DigitalOcean
export SECRET_KEY='paste-the-secret-key-from-digitalocean-here'
```

### Step 2: Activate Virtual Environment

```bash
# Create venv if it doesn't exist
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install python-jose if needed
python -m pip install 'python-jose[cryptography]'
```

### Step 3: Generate JWT Token

```bash
# Generate token with your user/account IDs
python3 scripts/generate_token.py 'your-user-id' 'your-account-id'

# Or use test values
python3 scripts/generate_token.py 'test-user-123' 'test-account-456'
```

**Copy the generated token** - you'll need it for the next steps.

---

## Part 3: Create Your First Site

### Step 1: Create a Site via API

Use the JWT token you just generated:

```bash
curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/sites \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My WordPress Site",
    "domain": "yourdomain.com"
  }'
```

**Response will include:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "My WordPress Site",
  "domain": "yourdomain.com",
  ...
}
```

**⚠️ IMPORTANT:** Copy the `id` value - this is your **Site ID**!

---

## Part 4: Generate an API Key

### Step 1: Generate API Key for Your Site

```bash
curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "YOUR_SITE_ID_FROM_STEP_3",
    "name": "WordPress Production Key",
    "scopes": ["read", "write"],
    "expires_in_days": null
  }'
```

**Response will include:**
```json
{
  "id": "...",
  "site_id": "...",
  "name": "WordPress Production Key",
  "key_prefix": "sk-abc12",
  "api_key": "sk-abc123def456..."  ← ⚠️ COPY THIS IMMEDIATELY!
  ...
}
```

**⚠️ CRITICAL:** Copy the `api_key` value immediately - it's only shown once!

---

## Part 5: Configure WordPress Plugin

### Step 1: Install Siloq Connector Plugin

1. In WordPress admin, go to **Plugins** → **Add New**
2. Upload the `siloq-connector-plugin.zip` file
3. Activate the plugin

### Step 2: Configure Plugin Settings

1. Go to **Settings** → **Siloq** (or **Siloq** in the sidebar)
2. Fill in the settings:

   **API URL:**
   ```
   https://siloq-app-edwlr.ondigitalocean.app/api/v1
   ```

   **API Key:**
   ```
   sk-abc123def456... (the API key you generated in Part 4)
   ```

   **Site ID:**
   ```
   123e4567-e89b-12d3-a456-426614174000 (from Part 3)
   ```

3. Click **Save Settings**

### Step 3: Test Connection

1. Click **Test API Connection** button
2. You should see: "Connection successful!"

### Step 4: Enable Auto-Sync (Optional)

- Check **Auto-Sync** to automatically sync pages when published
- Select which post types to sync (default: Pages and Posts)

---

## Part 6: Verify Everything Works

### Test 1: Health Check

```bash
curl https://siloq-app-edwlr.ondigitalocean.app/health
```

Should return:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### Test 2: List Your Sites

```bash
curl -X GET https://siloq-app-edwlr.ondigitalocean.app/api/v1/sites \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Test 3: Sync a WordPress Page

1. In WordPress, create or edit a page
2. Publish it
3. Check the sync status in **Siloq** → **Sync Status**

---

## Troubleshooting

### Issue: "Not authenticated" when creating site

**Solution:** 
- Make sure your JWT token is valid (not expired - they last 30 minutes)
- Regenerate token if needed
- Check token format: `Authorization: Bearer YOUR_TOKEN`

### Issue: "Site not found" when generating API key

**Solution:**
- Verify you're using the correct Site ID (UUID format)
- Make sure the site was created successfully

### Issue: WordPress plugin can't connect

**Solution:**
1. Verify API URL is correct: `https://siloq-app-edwlr.ondigitalocean.app/api/v1`
2. Check API key is correct (starts with `sk-`)
3. Verify Site ID matches
4. Check DigitalOcean app is running (visit the health endpoint)

### Issue: SECRET_KEY not found in DigitalOcean

**Solution:**
1. Go to App Settings → Environment Variables
2. Click **Edit** or **Add Variable**
3. Add:
   - **Key:** `SECRET_KEY`
   - **Value:** Generate one using:
     ```bash
     python3 -c "import secrets; print(secrets.token_urlsafe(32))"
     ```
4. **Scope:** App-Level
5. Save and restart your app

---

## Quick Reference: All URLs and Endpoints

### Your App URLs
- **App Root:** `https://siloq-app-edwlr.ondigitalocean.app`
- **API Base:** `https://siloq-app-edwlr.ondigitalocean.app/api/v1`
- **Health Check:** `https://siloq-app-edwlr.ondigitalocean.app/health`
- **API Docs:** `https://siloq-app-edwlr.ondigitalocean.app/docs` (if enabled)

### Key Endpoints
- `POST /api/v1/sites` - Create site
- `GET /api/v1/sites/{site_id}` - Get site
- `POST /api/v1/api-keys` - Generate API key
- `GET /api/v1/api-keys/site/{site_id}` - List API keys
- `POST /api/v1/pages` - Create page
- `GET /api/v1/pages/{page_id}` - Get page

---

## Environment Variables Checklist

Make sure these are set in DigitalOcean App Platform:

- ✅ `SECRET_KEY` - For JWT token generation
- ✅ `DATABASE_URL` - PostgreSQL connection
- ✅ `REDIS_URL` - Redis connection (if using)
- ✅ `OPENAI_API_KEY` - For AI content generation (if using)

To check/add variables:
1. App → Settings → Environment Variables
2. Add or edit as needed
3. **Restart app** after adding new variables

---

## Next Steps After Setup

1. **Create your first silo structure** (3-7 silos per site)
2. **Generate content** for your pages
3. **Set up governance rules** for your content
4. **Monitor sync status** in WordPress dashboard

---

## Support & Documentation

- **API Documentation:** Visit `/docs` endpoint (if Swagger is enabled)
- **WordPress Plugin Docs:** See `wordpress-plugin/README.md`
- **Architecture:** See `ARCHITECTURE.md`
- **Deployment Guide:** See `DEPLOYMENT_INSTRUCTIONS.md`

---

## Summary Checklist

- [ ] Got SECRET_KEY from DigitalOcean
- [ ] Generated JWT token locally
- [ ] Created a Site via API
- [ ] Generated API key for the site
- [ ] Configured WordPress plugin with:
  - [ ] API URL
  - [ ] API Key
  - [ ] Site ID
- [ ] Tested connection
- [ ] Verified health check works
- [ ] Synced first WordPress page

**You're all set!** 🎉
