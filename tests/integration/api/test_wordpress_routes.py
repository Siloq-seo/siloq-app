"""Integration tests for WordPress TALI API routes"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


@pytest.fixture
def client():
    """Create test client"""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def mock_project_id():
    """Mock project ID"""
    return str(uuid4())


@pytest.fixture
def mock_claim_id():
    """Mock claim ID"""
    return "CLAIM:SRV-12345678"


class TestWordPressThemeProfile:
    """Tests for theme profile sync endpoint"""
    
    @pytest.mark.integration
    def test_sync_theme_profile_requires_auth(self, client, mock_project_id):
        """Test that theme profile sync requires authentication"""
        profile_data = {
            "tali_version": "1.0",
            "platform": "wordpress",
            "theme": {
                "name": "Test Theme",
                "stylesheet": "test-theme",
                "is_block_theme": True
            },
            "tokens": {},
            "fingerprinted_at": "2026-01-09T12:00:00Z"
        }
        
        response = client.post(
            f"/api/v1/wordpress/projects/{mock_project_id}/theme-profile",
            json=profile_data
        )
        
        # Should require authentication
        assert response.status_code in [401, 403, 404]  # 404 if project doesn't exist, 401/403 if auth required


class TestWordPressClaimState:
    """Tests for claim state endpoint"""
    
    @pytest.mark.integration
    def test_get_claim_state_requires_auth(self, client, mock_claim_id):
        """Test that claim state endpoint requires authentication"""
        response = client.get(f"/api/v1/wordpress/claims/{mock_claim_id}/state")
        
        # Should require authentication
        assert response.status_code in [401, 403]


class TestWordPressPageSync:
    """Tests for page sync endpoint"""
    
    @pytest.mark.integration
    def test_sync_page_requires_auth(self, client, mock_project_id):
        """Test that page sync requires authentication"""
        page_data = {
            "wordpress_post_id": 123,
            "title": "Test Page",
            "path": "/test-page",
            "content": "Test content",
            "status": "publish"
        }
        
        response = client.post(
            f"/api/v1/wordpress/projects/{mock_project_id}/pages/sync",
            json=page_data
        )
        
        # Should require authentication
        assert response.status_code in [401, 403, 404]
