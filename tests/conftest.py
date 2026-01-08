"""Pytest configuration and shared fixtures"""
import pytest
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Test database URL (use in-memory SQLite for unit tests)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:"
)


@pytest.fixture
def test_settings():
    """Test settings override"""
    from app.core.config import Settings
    
    class TestSettings(Settings):
        database_url: str = TEST_DATABASE_URL
        database_url_sync: str = "sqlite:///:memory:"
        redis_url: str = "redis://localhost:6379/1"  # Use different DB for tests
        secret_key: str = "test-secret-key-for-testing-only"
        openai_api_key: str = "test-openai-key"
        environment: str = "test"
        global_generation_enabled: bool = True
    
    return TestSettings()


@pytest.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    from app.core.database import Base
    
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
        poolclass=StaticPool if "sqlite" in TEST_DATABASE_URL else None,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def mock_project_id():
    """Mock project UUID for testing"""
    from uuid import uuid4
    return uuid4()


@pytest.fixture
def mock_user_id():
    """Mock user UUID for testing"""
    from uuid import uuid4
    return uuid4()


@pytest.fixture
def mock_organization_id():
    """Mock organization UUID for testing"""
    from uuid import uuid4
    return uuid4()
