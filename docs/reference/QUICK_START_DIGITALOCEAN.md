# 🚀 Quick Start: DigitalOcean App Platform Setup

## TL;DR - Get Running in 5 Minutes

### 1. Get SECRET_KEY from DigitalOcean

```bash
# Go to: https://cloud.digitalocean.com/
# Apps → Your App → Settings → Environment Variables
# Copy SECRET_KEY value
```

### 2. Run Setup Script

```bash
cd /Users/jumar.juaton/Documents/GitHub/siloq
./scripts/setup_digitalocean.sh
```

The script will:
- ✅ Help you get SECRET_KEY
- ✅ Setup Python environment
- ✅ Generate JWT token
- ✅ Test API connection

### 3. Create Site & API Key

```bash
# Export your JWT token (from step 2)
export JWT_TOKEN="your-jwt-token-here"

# Create a site
curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/sites \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My WordPress Site", "domain": "yourdomain.com"}'

# Copy the site ID from response, then generate API key
curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/api-keys \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "YOUR_SITE_ID_HERE",
    "name": "WordPress Key",
    "scopes": ["read", "write"]
  }'
```

### 4. Configure WordPress

1. **Settings → Siloq**
2. **API URL:** `https://siloq-app-edwlr.ondigitalocean.app/api/v1`
3. **API Key:** (from step 3)
4. **Site ID:** (from step 3)
5. **Save & Test Connection**

---

## Full Guide

For detailed instructions, see: **DIGITALOCEAN_SETUP_GUIDE.md**

---

## Your App URLs

- **App:** https://siloq-app-edwlr.ondigitalocean.app
- **API:** https://siloq-app-edwlr.ondigitalocean.app/api/v1
- **Health:** https://siloq-app-edwlr.ondigitalocean.app/health

---

## Common Issues

**"Not authenticated"**
→ Regenerate JWT token (expires in 30 min)

**"Site not found"**
→ Verify Site ID is correct UUID

**WordPress can't connect**
→ Check API URL, API Key, and Site ID match

**SECRET_KEY not found**
→ Add it in DigitalOcean: App → Settings → Environment Variables
