#!/usr/bin/env python3
"""
Generate a JWT token for Siloq API authentication.

This script generates a JWT token using the same algorithm as the Siloq API.
You need to provide the SECRET_KEY from your .env file.

Usage:
    export SECRET_KEY="your-secret-key-here"
    python3 generate_token.py [user_id] [account_id]

Or set it inline:
    SECRET_KEY="your-secret-key" python3 generate_token.py

Example:
    SECRET_KEY="my-secret-key" python3 generate_token.py "user-123" "account-456"
"""
from dotenv import load_dotenv
load_dotenv()

import os
import sys
from datetime import datetime, timedelta
from jose import jwt

# Default expiration: 30 minutes (matching app settings)
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ALGORITHM = "HS256"

def create_access_token(data: dict, secret_key: str, expires_delta: timedelta = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def main():
    # Get secret key from environment
    secret_key = os.getenv("SECRET_KEY")
    
    if not secret_key:
        print("ERROR: SECRET_KEY environment variable is required!")
        print("\nUsage:")
        print("  export SECRET_KEY='your-secret-key-here'")
        print("  python3 generate_token.py [user_id] [account_id]")
        print("\nOr:")
        print("  SECRET_KEY='your-secret-key' python3 generate_token.py")
        sys.exit(1)
    
    # Get user_id and account_id from command line or use defaults
    user_id = sys.argv[1] if len(sys.argv) > 1 else "test-user-123"
    account_id = sys.argv[2] if len(sys.argv) > 2 else "test-account-456"
    
    # Create token payload
    token_data = {
        "sub": user_id,  # Subject (user ID) - required
        "account_id": account_id,  # Optional account ID
    }
    
    # Generate token
    token = create_access_token(token_data, secret_key)
    
    print("=" * 60)
    print("JWT Token Generated Successfully")
    print("=" * 60)
    print(f"\nUser ID: {user_id}")
    print(f"Account ID: {account_id}")
    print(f"\nToken (expires in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes):")
    print("-" * 60)
    print(token)
    print("-" * 60)
    print("\nUse this token in API requests:")
    print(f'Authorization: Bearer {token}')
    print("\nExample curl command:")
    print(f'curl -X POST https://siloq-app-edwlr.ondigitalocean.app/api/v1/sites \\')
    print('     -H "Authorization: Bearer ' + token + '" \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"name": "My WordPress Site", "domain": "yourdomain.com"}\'')
    print("=" * 60)

if __name__ == "__main__":
    main()
