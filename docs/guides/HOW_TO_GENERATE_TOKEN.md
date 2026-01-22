# Step-by-Step: How to Generate a JWT Token

## Complete Walkthrough

### Step 1: Get Your SECRET_KEY

The `SECRET_KEY` is stored in your environment. Here are ways to find it:

#### Option A: From Local .env File (If You Have One)

```bash
# Navigate to your project directory
cd /Users/jumar.juaton/Documents/GitHub/siloq

# Check if .env file exists and view SECRET_KEY
cat .env | grep SECRET_KEY

# Or use grep with better formatting
grep "^SECRET_KEY" .env
```

**Example output:**
```
SECRET_KEY=your-actual-secret-key-value-here
```

#### Option B: From DigitalOcean App Platform

1. Go to https://cloud.digitalocean.com/
2. Navigate to your **Apps** → Select your Siloq app
3. Go to **Settings** → **App-Level Environment Variables**
4. Find `SECRET_KEY` in the list
5. Click to reveal the value (or copy it)

#### Option C: From Your Deployment Environment

If you have SSH access to your server:

```bash
# SSH into your server
ssh your-server

# Check environment variable
echo $SECRET_KEY

# Or check in app configuration
# (depends on your deployment method)
```

#### Option D: Generate a New SECRET_KEY (For Testing)

If you just need a test key for development:

```bash
# Generate a random secret key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**⚠️ Note:** For production, use the same SECRET_KEY that your deployed app is using!

---

### Step 2: Export SECRET_KEY in Your Terminal

Once you have your SECRET_KEY, export it as an environment variable:

```bash
# Method 1: Export for current session (recommended)
export SECRET_KEY='your-actual-secret-key-value-here'

# Method 2: Inline (for one-time use)
SECRET_KEY='your-actual-secret-key-value-here' python3 scripts/generate_token.py
```

**Important Notes:**
- Use **single quotes** `'...'` to prevent zsh from interpreting special characters
- The export only lasts for your current terminal session
- Don't commit the SECRET_KEY to git!

**Verify it's set:**
```bash
echo $SECRET_KEY
# Should output your secret key
```

---

### Step 3: Activate Virtual Environment

Make sure you're in the project directory and activate the venv:

```bash
# Navigate to project
cd /Users/jumar.juaton/Documents/GitHub/siloq

# Activate virtual environment
source venv/bin/activate

# You should see (venv) in your prompt
```

---

### Step 4: Run the Token Generator

Now run the script with your user ID and account ID:

```bash
# Basic usage (uses default test values)
python3 scripts/generate_token.py

# With custom user ID
python3 scripts/generate_token.py 'my-user-id'

# With custom user ID and account ID
python3 scripts/generate_token.py 'my-user-id' 'my-account-id'
```

**Example:**
```bash
python3 scripts/generate_token.py 'user-123' 'account-456'
```

**What happens:**
- The script reads `SECRET_KEY` from environment
- Generates a JWT token valid for 30 minutes
- Displays the token and example usage

---

## Complete Example (Copy & Paste)

```bash
# 1. Navigate to project
cd /Users/jumar.juaton/Documents/GitHub/siloq

# 2. Activate virtual environment
source venv/bin/activate

# 3. Export your SECRET_KEY (replace with your actual key)
export SECRET_KEY='your-secret-key-from-env-or-deployment'

# 4. Generate token
python3 scripts/generate_token.py 'user-123' 'account-456'
```

**Expected Output:**
```
============================================================
JWT Token Generated Successfully
============================================================

User ID: user-123
Account ID: account-456

Token (expires in 30 minutes):
------------------------------------------------------------
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImFjY291bnRfaWQiOiJhY2NvdW50LTQ1NiIsImV4cCI6MTczNzU2MTYwMH0.xxxxx
------------------------------------------------------------

Use this token in API requests:
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

Example curl command:
curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/sites \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     -H "Content-Type: application/json" \
     -d '{"name": "My WordPress Site", "domain": "yourdomain.com"}'
============================================================
```

---

## Troubleshooting

### Error: "SECRET_KEY environment variable is required!"

**Solution:** Make sure you exported it:
```bash
export SECRET_KEY='your-key-here'
echo $SECRET_KEY  # Verify it's set
```

### Error: "ModuleNotFoundError: No module named 'jose'"

**Solution:** Install python-jose:
```bash
source venv/bin/activate
python -m pip install 'python-jose[cryptography]'
```

### Error: "unknown command" when installing

**Solution:** Use `python -m pip` instead of `pip`:
```bash
python -m pip install 'python-jose[cryptography]'
```

---

## Quick Reference

```bash
# One-liner (if SECRET_KEY is already in your environment)
cd /Users/jumar.juaton/Documents/GitHub/siloq && \
source venv/bin/activate && \
python3 scripts/generate_token.py 'user-123' 'account-456'

# Or with inline SECRET_KEY
cd /Users/jumar.juaton/Documents/GitHub/siloq && \
source venv/bin/activate && \
SECRET_KEY='your-key' python3 scripts/generate_token.py 'user-123' 'account-456'
```

---

## Next Steps

After generating the token:

1. **Copy the token** from the output
2. **Use it in API requests:**
   ```bash
   curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/sites \
     -H "Authorization: Bearer YOUR_TOKEN_HERE" \
     -H "Content-Type: application/json" \
     -d '{"name": "My WordPress Site", "domain": "yourdomain.com"}'
   ```
3. **Token expires in 30 minutes** - generate a new one when needed
