"""Security utilities for encryption, API key handling, and tenant isolation"""
import os
import base64
import hashlib
import hmac
from typing import Optional, Dict, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


class SecurityError(Exception):
    """Security-related error"""
    pass


class EncryptionManager:
    """AES-256-GCM encryption manager for sensitive data"""
    
    def __init__(self):
        # Master key from environment (32 bytes = 256 bits)
        master_key_env = os.getenv("SILOQ_MASTER_ENCRYPTION_KEY")
        if not master_key_env:
            raise SecurityError("SILOQ_MASTER_ENCRYPTION_KEY environment variable is required")
        
        # Derive encryption key from master key using PBKDF2
        self.master_key = master_key_env.encode('utf-8') if isinstance(master_key_env, str) else master_key_env
        
        # Ensure master key is 32 bytes
        if len(self.master_key) != 32:
            # Hash to get 32 bytes if needed
            self.master_key = hashlib.sha256(self.master_key).digest()
    
    def derive_key(self, project_id: str) -> bytes:
        """
        Derive project-specific encryption key from master key.
        
        Args:
            project_id: Project UUID as string
            
        Returns:
            32-byte encryption key
        """
        # Use PBKDF2 to derive project-specific key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=project_id.encode('utf-8'),
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(self.master_key)
    
    def encrypt(self, plaintext: str, project_id: str) -> Dict[str, str]:
        """
        Encrypt plaintext using AES-256-GCM.
        
        Args:
            plaintext: Text to encrypt
            project_id: Project UUID for key derivation
            
        Returns:
            Dictionary with encrypted, iv, and auth_tag (all base64-encoded)
        """
        if not plaintext:
            raise SecurityError("Cannot encrypt empty plaintext")
        
        # Derive project-specific key
        key = self.derive_key(project_id)
        
        # Generate random IV (12 bytes for GCM)
        iv = os.urandom(12)
        
        # Encrypt
        aesgcm = AESGCM(key)
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = aesgcm.encrypt(iv, plaintext_bytes, None)
        
        # GCM produces ciphertext + auth_tag (last 16 bytes)
        # In our case, auth_tag is returned separately
        # Actually, AESGCM.encrypt returns ciphertext with auth_tag appended
        # We need to separate them
        ciphertext_with_tag = ciphertext
        auth_tag = ciphertext_with_tag[-16:]
        encrypted = ciphertext_with_tag[:-16]
        
        return {
            "encrypted": base64.b64encode(encrypted).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "auth_tag": base64.b64encode(auth_tag).decode('utf-8')
        }
    
    def decrypt(self, encrypted_data: Dict[str, str], project_id: str) -> str:
        """
        Decrypt ciphertext using AES-256-GCM.
        
        Args:
            encrypted_data: Dictionary with encrypted, iv, and auth_tag (all base64-encoded)
            project_id: Project UUID for key derivation
            
        Returns:
            Decrypted plaintext
        """
        if not encrypted_data.get("encrypted") or not encrypted_data.get("iv") or not encrypted_data.get("auth_tag"):
            raise SecurityError("Invalid encrypted data format")
        
        try:
            # Decode base64
            encrypted = base64.b64decode(encrypted_data["encrypted"])
            iv = base64.b64decode(encrypted_data["iv"])
            auth_tag = base64.b64decode(encrypted_data["auth_tag"])
            
            # Reconstruct ciphertext + auth_tag
            ciphertext_with_tag = encrypted + auth_tag
            
            # Derive project-specific key
            key = self.derive_key(project_id)
            
            # Decrypt
            aesgcm = AESGCM(key)
            plaintext_bytes = aesgcm.decrypt(iv, ciphertext_with_tag, None)
            
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            raise SecurityError(f"Decryption failed: {str(e)}")
    
    def hash_payload(self, payload: Dict) -> str:
        """
        Generate SHA-256 hash of payload JSON for integrity verification.
        
        Args:
            payload: JSON-serializable dictionary
            
        Returns:
            Hexadecimal hash string
        """
        import json
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()


# Global encryption manager instance
_encryption_manager: Optional[EncryptionManager] = None


def get_encryption_manager() -> EncryptionManager:
    """Get global encryption manager instance"""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


class APIKeyManager:
    """Manager for BYOK (Bring Your Own Key) API key encryption/decryption"""
    
    def __init__(self, encryption_manager: Optional[EncryptionManager] = None):
        self.encryption_manager = encryption_manager or get_encryption_manager()
    
    def encrypt_api_key(self, api_key: str, project_id: str) -> Dict[str, str]:
        """
        Encrypt API key for storage.
        
        Args:
            api_key: Plaintext API key
            project_id: Project UUID
            
        Returns:
            Dictionary with encrypted, iv, and auth_tag
        """
        if not api_key or not api_key.strip():
            raise SecurityError("API key cannot be empty")
        
        return self.encryption_manager.encrypt(api_key, project_id)
    
    def decrypt_api_key(self, encrypted_data: Dict[str, str], project_id: str) -> str:
        """
        Decrypt API key for use (never display).
        
        Args:
            encrypted_data: Encrypted API key data
            project_id: Project UUID
            
        Returns:
            Decrypted API key
        """
        return self.encryption_manager.decrypt(encrypted_data, project_id)
    
    def mask_api_key(self, api_key: str) -> str:
        """
        Mask API key for display (show last 4 characters only).
        
        Args:
            api_key: Full API key
            
        Returns:
            Masked key string (e.g., "sk-••••••••••••abc123")
        """
        if not api_key or len(api_key) <= 4:
            return "••••••••"
        
        prefix = api_key[:3] if len(api_key) > 3 else ""
        last_four = api_key[-4:]
        masked_length = max(8, len(api_key) - 7)
        
        return f"{prefix}{'•' * masked_length}{last_four}"


def validate_api_key_format(api_key: str, provider: str) -> bool:
    """
    Validate API key format for a provider.
    
    Args:
        api_key: API key to validate
        provider: Provider name (openai, anthropic, google)
        
    Returns:
        True if format appears valid
    """
    if not api_key or not api_key.strip():
        return False
    
    api_key = api_key.strip()
    
    if provider == "openai":
        # OpenAI keys start with "sk-"
        return api_key.startswith("sk-") and len(api_key) > 10
    elif provider == "anthropic":
        # Anthropic keys start with "sk-ant-"
        return api_key.startswith("sk-ant-") and len(api_key) > 10
    elif provider == "google":
        # Google API keys are typically longer
        return len(api_key) > 20
    else:
        # Unknown provider - basic validation
        return len(api_key) > 5


def sanitize_user_input(input_str: str, allow_html: bool = False) -> str:
    """
    Sanitize user input to prevent XSS attacks.
    
    Args:
        input_str: Input string to sanitize
        allow_html: If True, allow safe HTML tags (for content fields)
        
    Returns:
        Sanitized string
    """
    if not input_str:
        return ""
    
    # Basic XSS prevention - remove script tags and dangerous patterns
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'onerror=',
        r'onload=',
        r'onclick=',
        r'onmouseover=',
        r'eval\(',
        r'expression\(',
    ]
    
    import re
    sanitized = input_str
    
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    if not allow_html:
        # Remove all HTML tags
        sanitized = re.sub(r'<[^>]+>', '', sanitized)
    
    return sanitized.strip()
