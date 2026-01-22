"""Unit tests for API helper utilities"""
import pytest
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.utils.database import get_or_404, get_or_none
from app.utils.responses import format_error_response, format_success_response


class TestDatabaseHelpers:
    """Tests for database helper functions"""
    
    @pytest.mark.asyncio
    async def test_get_or_404_found(self):
        """Test get_or_404 when entity exists"""
        # Mock database session and entity
        mock_entity = MagicMock()
        mock_entity.id = uuid4()
        mock_entity.name = "Test Entity"
        
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_entity)
        
        # Mock model class
        class MockModel:
            __name__ = "MockModel"
        
        # Should return the entity
        result = await get_or_404(mock_db, MockModel, mock_entity.id, "MockModel")
        assert result.id == mock_entity.id
        assert result.name == "Test Entity"
    
    @pytest.mark.asyncio
    async def test_get_or_404_not_found(self):
        """Test get_or_404 when entity doesn't exist"""
        fake_id = uuid4()
        
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)
        
        class MockModel:
            __name__ = "MockModel"
        
        # Should raise 404
        with pytest.raises(HTTPException) as exc_info:
            await get_or_404(mock_db, MockModel, fake_id, "MockModel")
        
        assert exc_info.value.status_code == 404
        assert "MockModel not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_get_or_none_found(self):
        """Test get_or_none when entity exists"""
        mock_entity = MagicMock()
        mock_entity.id = uuid4()
        
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_entity)
        
        class MockModel:
            pass
        
        result = await get_or_none(mock_db, MockModel, mock_entity.id)
        assert result is not None
        assert result.id == mock_entity.id
    
    @pytest.mark.asyncio
    async def test_get_or_none_not_found(self):
        """Test get_or_none when entity doesn't exist"""
        fake_id = uuid4()
        
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)
        
        class MockModel:
            pass
        
        result = await get_or_none(mock_db, MockModel, fake_id)
        assert result is None


class TestResponseHelpers:
    """Tests for response formatting utilities"""
    
    def test_format_error_response_basic(self):
        """Test basic error response formatting"""
        response = format_error_response("Something went wrong")
        
        assert "error" in response
        assert response["error"] == "Something went wrong"
    
    def test_format_error_response_with_code(self):
        """Test error response with error code"""
        response = format_error_response(
            "Validation failed",
            error_code="VALIDATION_001"
        )
        
        assert response["error"] == "Validation failed"
        assert response["error_code"] == "VALIDATION_001"
    
    def test_format_error_response_with_extra_fields(self):
        """Test error response with additional fields"""
        response = format_error_response(
            "Invalid input",
            error_code="VALIDATION_001",
            field="email",
            value="invalid"
        )
        
        assert response["error"] == "Invalid input"
        assert response["error_code"] == "VALIDATION_001"
        assert response["field"] == "email"
        assert response["value"] == "invalid"
    
    def test_format_success_response_basic(self):
        """Test basic success response formatting"""
        response = format_success_response("Operation successful")
        
        assert "message" in response
        assert response["message"] == "Operation successful"
    
    def test_format_success_response_with_data(self):
        """Test success response with data"""
        response = format_success_response(
            "Site created",
            data={"site_id": "123", "name": "Test Site"}
        )
        
        assert response["message"] == "Site created"
        assert "data" in response
        assert response["data"]["site_id"] == "123"
        assert response["data"]["name"] == "Test Site"
    
    def test_format_success_response_with_extra_fields(self):
        """Test success response with additional fields"""
        response = format_success_response(
            "Created",
            data={"id": "123"},
            timestamp="2026-01-21T10:00:00Z"
        )
        
        assert response["message"] == "Created"
        assert response["data"]["id"] == "123"
        assert response["timestamp"] == "2026-01-21T10:00:00Z"
