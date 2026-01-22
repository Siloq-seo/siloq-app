"""Unit tests for page service"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.content import PageService
from app.db.models import Page, ContentStatus, Site


class TestPageService:
    """Tests for PageService"""
    
    @pytest.mark.asyncio
    async def test_page_service_initialization(self, test_db_session):
        """Test PageService initializes correctly"""
        service = PageService(test_db_session)
        
        assert service.db == test_db_session
        assert service.gate_manager is not None
        assert service.publishing_safety is not None
    
    @pytest.mark.asyncio
    async def test_check_publish_gates(self, test_db_session):
        """Test checking publish gates for a page"""
        # Create test site and page
        site = Site(name="Test Site", domain="test.com")
        test_db_session.add(site)
        await test_db_session.commit()
        
        page = Page(
            site_id=site.id,
            path="/test-page",
            title="Test Page",
            body="Test content",
            status=ContentStatus.DRAFT
        )
        test_db_session.add(page)
        await test_db_session.commit()
        
        service = PageService(test_db_session)
        
        # Mock gate manager to return passed gates
        with patch.object(service.gate_manager, 'check_all_gates', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {
                "all_passed": True,
                "gates": {}
            }
            
            result = await service.check_publish_gates(page.id)
            
            assert result is not None
            mock_check.assert_called_once()
