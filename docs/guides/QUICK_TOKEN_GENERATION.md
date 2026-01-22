# Quick JWT Token Generation Guide

## ✅ Fixed: zsh Installation Issue

**Root Cause:** You have a custom `pip` shell function in zsh that intercepts the `pip` command and doesn't handle brackets correctly.

**The Solutions:**
1. ✅ Use `python -m pip` (bypasses the function - RECOMMENDED)
2. ✅ Use `command pip` (bypasses the function)
3. ❌ Don't use `pip` directly (triggers the broken function)

## Step-by-Step Instructions

### 1. Create and activate virtual environment

```bash
cd /Users/jumar.juaton/Documents/GitHub/siloq
python3 -m venv venv
source venv/bin/activate
```

### 2. Install python-jose (FIXED for zsh)

```bash
# ✅ CORRECT - Use python -m pip
python -m pip install 'python-jose[cryptography]'

# ❌ WRONG - This causes "unknown command" error in zsh
pip install 'python-jose[cryptography]'
```

### 3. Get your SECRET_KEY

You need the `SECRET_KEY` from your Siloq deployment. Options:

**Option A: From local .env file (if you have one)**
```bash
grep SECRET_KEY .env
```

**Option B: From DigitalOcean App Platform**
1. Go to your DigitalOcean dashboard
2. Navigate to your Siloq app
3. Go to Settings → Environment Variables
4. Find `SECRET_KEY` and copy its value

**Option C: From your deployment environment**
```bash
# If you have SSH access
echo $SECRET_KEY
```

### 4. Generate the token

```bash
# Make sure venv is activated
source venv/bin/activate

# Set SECRET_KEY and generate token
export SECRET_KEY="your-secret-key-here"
python3 scripts/generate_token.py "user-123" "account-456"

# Or inline:
SECRET_KEY="your-secret-key" python3 scripts/generate_token.py "user-123" "account-456"
```

### 5. Use the token

Copy the generated token and use it in your API requests:

```bash
curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/sites \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"name": "My WordPress Site", "domain": "yourdomain.com"}'
```

## Alternative: Use jwt.io (No Installation Needed)

If you don't want to install dependencies:

1. Go to https://jwt.io/
2. Algorithm: **HS256**
3. Secret: Your `SECRET_KEY`
4. Payload:
   ```json
   {
     "sub": "user-123",
     "account_id": "account-456",
     "exp": 1737561600
   }
   ```
   (Replace `exp` with: current Unix timestamp + 1800 seconds for 30 minutes)
5. Copy the generated token

## Summary

**Key Fix for zsh:**
- ✅ Use: `python -m pip install 'python-jose[cryptography]'`
- ❌ Avoid: `pip install 'python-jose[cryptography]'`

The `python -m pip` approach ensures the command is properly executed as a Python module, avoiding zsh's bracket expansion issues.
