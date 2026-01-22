"""Unit tests for website scanner service"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.scanning import WebsiteScanner


class TestWebsiteScanner:
    """Tests for WebsiteScanner service"""
    
    @pytest.mark.asyncio
    async def test_scanner_initialization(self):
        """Test scanner initializes with correct defaults"""
        scanner = WebsiteScanner()
        
        assert scanner.timeout == 30
        assert scanner.max_pages == 10
        assert scanner.client is None
    
    @pytest.mark.asyncio
    async def test_scanner_context_manager(self):
        """Test scanner works as async context manager"""
        async with WebsiteScanner() as scanner:
            assert scanner.client is not None
    
    @pytest.mark.asyncio
    async def test_calculate_grade(self):
        """Test grade calculation from score"""
        scanner = WebsiteScanner()
        
        assert scanner._calculate_grade(100.0) == "A+"
        assert scanner._calculate_grade(97.0) == "A+"
        assert scanner._calculate_grade(95.0) == "A"
        assert scanner._calculate_grade(90.0) == "B+"
        assert scanner._calculate_grade(85.0) == "B"
        assert scanner._calculate_grade(80.0) == "C+"
        assert scanner._calculate_grade(75.0) == "C"
        assert scanner._calculate_grade(70.0) == "D+"
        assert scanner._calculate_grade(65.0) == "D"
        assert scanner._calculate_grade(50.0) == "F"
    
    def test_get_recommendation_action(self):
        """Test recommendation action generation"""
        scanner = WebsiteScanner()
        
        action = scanner._get_recommendation_action("Not using HTTPS")
        assert "HTTPS" in action or "SSL" in action
        
        action = scanner._get_recommendation_action("Missing title tag")
        assert "title" in action.lower()
        
        action = scanner._get_recommendation_action("Missing canonical link")
        assert "canonical" in action.lower()
    
    @pytest.mark.asyncio
    async def test_generate_recommendations(self):
        """Test recommendation generation from scan results"""
        scanner = WebsiteScanner()
        
        results = {
            "technical_details": {
                "issues": ["Not using HTTPS", "Missing viewport meta tag"]
            },
            "content_details": {
                "issues": ["Missing title tag", "Title tag too short"]
            },
            "structure_details": {
                "issues": ["No navigation structure found"]
            },
            "performance_details": {
                "issues": ["Slow response time: 5000ms"]
            }
        }
        
        recommendations = scanner._generate_recommendations(results)
        
        assert len(recommendations) > 0
        assert all("category" in rec for rec in recommendations)
        assert all("priority" in rec for rec in recommendations)
        assert all("issue" in rec for rec in recommendations)
        assert all("action" in rec for rec in recommendations)
