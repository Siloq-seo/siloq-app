"""Unit tests for tenant isolation module"""
import pytest
from app.core.security.tenant_isolation import (
    validate_prompt_isolation,
    FORBIDDEN_PROMPT_PATTERNS,
    TenantIsolationError,
)


class TestPromptIsolation:
    """Tests for prompt isolation validation"""
    
    def test_validate_prompt_isolation_allows_valid_data(self):
        """Test that valid prompt data passes validation"""
        valid_prompt = {
            "page_id": "123",
            "page_type": "service",
            "intent": "commercial",
            "primary_keyword": "plumber",
            "entities": ["entity1", "entity2"],
            "target_summary": "Brief summary"
        }
        
        forbidden_keys = validate_prompt_isolation(valid_prompt, "project-123")
        assert len(forbidden_keys) == 0
    
    def test_validate_prompt_isolation_blocks_forbidden_patterns(self):
        """Test that forbidden patterns are detected"""
        invalid_prompt = {
            "page_id": "123",
            "full_sitemap": ["page1", "page2"],  # Forbidden
            "global_keyword_list": ["kw1", "kw2"],  # Forbidden
            "other_client_data": "data"  # Forbidden
        }
        
        forbidden_keys = validate_prompt_isolation(invalid_prompt, "project-123")
        
        assert len(forbidden_keys) > 0
        assert any("full_sitemap" in key for key in forbidden_keys)
        assert any("global_keyword_list" in key for key in forbidden_keys)
        assert any("other_client_data" in key for key in forbidden_keys)
    
    def test_validate_prompt_isolation_detects_nested_forbidden_data(self):
        """Test that nested forbidden data is detected"""
        invalid_prompt = {
            "page_data": {
                "content": "valid",
                "metadata": {
                    "competitor_urls": ["url1", "url2"]  # Forbidden nested
                }
            }
        }
        
        forbidden_keys = validate_prompt_isolation(invalid_prompt, "project-123")
        
        assert len(forbidden_keys) > 0
        assert any("competitor_urls" in key for key in forbidden_keys)
    
    def test_forbidden_patterns_list(self):
        """Test that FORBIDDEN_PROMPT_PATTERNS contains expected patterns"""
        assert "full_sitemap" in FORBIDDEN_PROMPT_PATTERNS
        assert "global_keyword_list" in FORBIDDEN_PROMPT_PATTERNS
        assert "other_client_data" in FORBIDDEN_PROMPT_PATTERNS
        assert "cross_project" in FORBIDDEN_PROMPT_PATTERNS
        assert len(FORBIDDEN_PROMPT_PATTERNS) > 0
