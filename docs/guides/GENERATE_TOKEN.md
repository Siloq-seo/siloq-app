# How to Generate a JWT Token for Siloq API

## Option 1: Using the Python Script (Recommended)

### Step 1: Install the required dependency

**Important:** Use `python -m pip` instead of `pip` directly to avoid zsh bracket expansion issues.

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install using python -m pip (this avoids zsh issues)
python -m pip install 'python-jose[cryptography]'
```

**Note:** If you get "unknown command" errors, always use `python -m pip` instead of just `pip`.

### Step 2: Get your SECRET_KEY

The SECRET_KEY is stored in your `.env` file or environment variables. You can find it by:

```bash
# If you have access to the server/environment
echo $SECRET_KEY

# Or check your .env file (if local)
grep SECRET_KEY .env
```

### Step 3: Generate the token

```bash
# Set the secret key and run the script
SECRET_KEY="your-secret-key-here" python3 scripts/generate_token.py "user-123" "account-456"

# Or export it first
export SECRET_KEY="your-secret-key-here"
python3 scripts/generate_token.py "user-123" "account-456"
```

## Option 2: Using an Online JWT Generator

1. Go to https://jwt.io/
2. Select algorithm: **HS256**
3. Enter your **SECRET_KEY** in the "Verify Signature" section
4. In the "Payload" section, enter:
   ```json
   {
     "sub": "user-123",
     "account_id": "account-456",
     "exp": 1737561600
   }
   ```
   (Replace `exp` with a future Unix timestamp, e.g., current time + 30 minutes)
5. Copy the generated token from the left side

## Option 3: Using Python Interactively

```python
from datetime import datetime, timedelta
from jose import jwt
import os

# Set your secret key
SECRET_KEY = "your-secret-key-here"

# Create payload
token_data = {
    "sub": "user-123",  # User ID
    "account_id": "account-456",  # Account ID (optional)
    "exp": datetime.utcnow() + timedelta(minutes=30)  # Expires in 30 minutes
}

# Generate token
token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
print(token)
```

## Option 4: Quick Test Token (For Development Only)

If you just need a token for testing and don't have the SECRET_KEY, you can temporarily modify the auth check or use a test secret. **This is NOT recommended for production.**

## Getting Your SECRET_KEY

### From Local Development:
```bash
cat .env | grep SECRET_KEY
```

### From Production/Deployed Environment:
- Check your DigitalOcean App Platform environment variables
- Check your deployment configuration
- Check your secrets management system

## Token Usage

Once you have the token, use it in API requests:

```bash
curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/sites \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"name": "My WordPress Site", "domain": "yourdomain.com"}'
```

## Token Expiration

- Default expiration: **30 minutes**
- After expiration, you'll need to generate a new token
- For long-term access, consider using API keys instead (they don't expire unless revoked)
