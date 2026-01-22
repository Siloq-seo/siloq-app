"""Unit tests for authentication utilities"""
import pytest
from datetime import timedelta
from app.core.auth import (
    create_access_token,
    decode_access_token,
    hash_api_key,
)


class TestTokenGeneration:
    """Tests for JWT token generation"""
    
    def test_create_access_token(self):
        """Test creating access token"""
        data = {"sub": "user-123", "account_id": "account-456"}
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_access_token_with_expiration(self):
        """Test creating token with custom expiration"""
        data = {"sub": "user-123"}
        expires_delta = timedelta(minutes=60)
        token = create_access_token(data, expires_delta=expires_delta)
        
        assert token is not None
        # Decode to verify expiration
        payload = decode_access_token(token)
        assert "exp" in payload
        assert "sub" in payload
        assert payload["sub"] == "user-123"
    
    def test_decode_access_token_valid(self):
        """Test decoding valid token"""
        data = {"sub": "user-123", "account_id": "account-456"}
        token = create_access_token(data)
        
        payload = decode_access_token(token)
        
        assert payload["sub"] == "user-123"
        assert payload["account_id"] == "account-456"
        assert "exp" in payload
    
    def test_decode_access_token_invalid(self):
        """Test decoding invalid token raises error"""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(Exception):  # Should raise AuthError or JWTError
            decode_access_token(invalid_token)


class TestAPIKeyHashing:
    """Tests for API key hashing"""
    
    def test_hash_api_key(self):
        """Test hashing API key"""
        api_key = "sk-test-key-12345"
        hash_value = hash_api_key(api_key)
        
        assert hash_value is not None
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 produces 64 char hex string
    
    def test_hash_api_key_deterministic(self):
        """Test that hashing same key produces same hash"""
        api_key = "sk-test-key-12345"
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)
        
        assert hash1 == hash2
    
    def test_hash_api_key_different_keys(self):
        """Test that different keys produce different hashes"""
        key1 = "sk-key-1"
        key2 = "sk-key-2"
        
        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)
        
        assert hash1 != hash2
