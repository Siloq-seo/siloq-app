"""Unit tests for encryption module"""
import pytest
import os
from app.core.security.encryption import (
    EncryptionManager,
    get_encryption_manager,
    APIKeyManager,
    validate_api_key_format,
    sanitize_user_input,
    SecurityError,
)


class TestEncryptionManager:
    """Tests for EncryptionManager"""
    
    def test_encryption_manager_requires_master_key(self):
        """Test that EncryptionManager requires master key"""
        # Temporarily remove master key
        original_key = os.environ.get("SILOQ_MASTER_ENCRYPTION_KEY")
        if "SILOQ_MASTER_ENCRYPTION_KEY" in os.environ:
            del os.environ["SILOQ_MASTER_ENCRYPTION_KEY"]
        
        try:
            with pytest.raises(SecurityError, match="SILOQ_MASTER_ENCRYPTION_KEY"):
                EncryptionManager()
        finally:
            # Restore original key
            if original_key:
                os.environ["SILOQ_MASTER_ENCRYPTION_KEY"] = original_key
    
    def test_encrypt_decrypt_roundtrip(self, monkeypatch):
        """Test encryption and decryption roundtrip"""
        # Set test master key (32 bytes)
        test_key = "a" * 32
        monkeypatch.setenv("SILOQ_MASTER_ENCRYPTION_KEY", test_key)
        
        manager = EncryptionManager()
        project_id = "test-project-123"
        plaintext = "test-api-key-sk-1234567890abcdef"
        
        # Encrypt
        encrypted_data = manager.encrypt(plaintext, project_id)
        
        # Verify structure
        assert "encrypted" in encrypted_data
        assert "iv" in encrypted_data
        assert "auth_tag" in encrypted_data
        assert encrypted_data["encrypted"] != plaintext
        
        # Decrypt
        decrypted = manager.decrypt(encrypted_data, project_id)
        
        # Verify roundtrip
        assert decrypted == plaintext
    
    def test_encrypt_empty_plaintext_raises_error(self, monkeypatch):
        """Test that encrypting empty plaintext raises error"""
        test_key = "a" * 32
        monkeypatch.setenv("SILOQ_MASTER_ENCRYPTION_KEY", test_key)
        
        manager = EncryptionManager()
        project_id = "test-project-123"
        
        with pytest.raises(SecurityError, match="Cannot encrypt empty plaintext"):
            manager.encrypt("", project_id)
    
    def test_decrypt_invalid_data_raises_error(self, monkeypatch):
        """Test that decrypting invalid data raises error"""
        test_key = "a" * 32
        monkeypatch.setenv("SILOQ_MASTER_ENCRYPTION_KEY", test_key)
        
        manager = EncryptionManager()
        project_id = "test-project-123"
        
        # Invalid encrypted data
        invalid_data = {"encrypted": "invalid", "iv": "invalid"}
        
        with pytest.raises(SecurityError, match="Decryption failed"):
            manager.decrypt(invalid_data, project_id)
    
    def test_hash_payload(self, monkeypatch):
        """Test payload hashing"""
        test_key = "a" * 32
        monkeypatch.setenv("SILOQ_MASTER_ENCRYPTION_KEY", test_key)
        
        manager = EncryptionManager()
        
        payload1 = {"key": "value", "number": 123}
        payload2 = {"number": 123, "key": "value"}  # Same keys, different order
        
        hash1 = manager.hash_payload(payload1)
        hash2 = manager.hash_payload(payload2)
        
        # Hashes should be same (sorted keys)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex = 64 chars
        
        # Different payload should have different hash
        payload3 = {"key": "different"}
        hash3 = manager.hash_payload(payload3)
        assert hash1 != hash3


class TestAPIKeyManager:
    """Tests for APIKeyManager"""
    
    def test_encrypt_api_key(self, monkeypatch):
        """Test API key encryption"""
        test_key = "a" * 32
        monkeypatch.setenv("SILOQ_MASTER_ENCRYPTION_KEY", test_key)
        
        api_key_manager = APIKeyManager()
        api_key = "sk-test-1234567890abcdef"
        project_id = "test-project-123"
        
        encrypted = api_key_manager.encrypt_api_key(api_key, project_id)
        
        assert "encrypted" in encrypted
        assert "iv" in encrypted
        assert "auth_tag" in encrypted
    
    def test_decrypt_api_key(self, monkeypatch):
        """Test API key decryption"""
        test_key = "a" * 32
        monkeypatch.setenv("SILOQ_MASTER_ENCRYPTION_KEY", test_key)
        
        api_key_manager = APIKeyManager()
        api_key = "sk-test-1234567890abcdef"
        project_id = "test-project-123"
        
        encrypted = api_key_manager.encrypt_api_key(api_key, project_id)
        decrypted = api_key_manager.decrypt_api_key(encrypted, project_id)
        
        assert decrypted == api_key
    
    def test_mask_api_key(self):
        """Test API key masking"""
        api_key_manager = APIKeyManager()
        
        # Test full key
        api_key = "sk-test-1234567890abcdef"
        masked = api_key_manager.mask_api_key(api_key)
        
        assert "sk-" in masked
        assert "abcdef" in masked  # Last 4 chars
        assert "•" in masked or "*" in masked  # Masked characters
        
        # Test short key
        short_key = "sk-123"
        masked_short = api_key_manager.mask_api_key(short_key)
        assert len(masked_short) > 0


class TestAPIKeyValidation:
    """Tests for API key format validation"""
    
    def test_validate_openai_key(self):
        """Test OpenAI API key validation"""
        assert validate_api_key_format("sk-test1234567890", "openai") is True
        assert validate_api_key_format("sk-", "openai") is False  # Too short
        assert validate_api_key_format("invalid", "openai") is False  # Wrong prefix
    
    def test_validate_anthropic_key(self):
        """Test Anthropic API key validation"""
        assert validate_api_key_format("sk-ant-test1234567890", "anthropic") is True
        assert validate_api_key_format("sk-test", "anthropic") is False  # Wrong prefix
    
    def test_validate_google_key(self):
        """Test Google API key validation"""
        assert validate_api_key_format("AIzaSyTest1234567890abcdefghijklmnop", "google") is True
        assert validate_api_key_format("short", "google") is False  # Too short
    
    def test_validate_empty_key(self):
        """Test that empty keys are invalid"""
        assert validate_api_key_format("", "openai") is False
        assert validate_api_key_format(None, "openai") is False


class TestInputSanitization:
    """Tests for user input sanitization"""
    
    def test_sanitize_removes_script_tags(self):
        """Test that script tags are removed"""
        input_str = '<script>alert("xss")</script>Hello'
        sanitized = sanitize_user_input(input_str)
        
        assert "<script>" not in sanitized
        assert "Hello" in sanitized
    
    def test_sanitize_removes_javascript_protocol(self):
        """Test that javascript: protocol is removed"""
        input_str = '<a href="javascript:alert(1)">Click</a>'
        sanitized = sanitize_user_input(input_str)
        
        assert "javascript:" not in sanitized
    
    def test_sanitize_removes_event_handlers(self):
        """Test that event handlers are removed"""
        input_str = '<img onerror="alert(1)" src="test.jpg">'
        sanitized = sanitize_user_input(input_str)
        
        assert "onerror" not in sanitized
    
    def test_sanitize_removes_html_when_not_allowed(self):
        """Test that HTML is removed when allow_html=False"""
        input_str = '<p>Hello <strong>World</strong></p>'
        sanitized = sanitize_user_input(input_str, allow_html=False)
        
        assert "<p>" not in sanitized
        assert "<strong>" not in sanitized
        assert "Hello World" in sanitized
    
    def test_sanitize_preserves_safe_content(self):
        """Test that safe content is preserved"""
        input_str = "Hello, this is safe content!"
        sanitized = sanitize_user_input(input_str)
        
        assert sanitized == input_str
