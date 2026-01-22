"""API Key management routes for WordPress plugin integration"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional, List
import secrets
import hashlib

from app.core.database import get_db
from app.core.auth import get_current_user, hash_api_key
from app.db.models import APIKey, Site

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class APIKeyCreate(BaseModel):
    """API key creation request"""
    site_id: UUID
    name: str
    scopes: List[str] = ["read", "write"]
    expires_in_days: Optional[int] = None  # None = never expires


class APIKeyResponse(BaseModel):
    """API key response (includes the actual key only on creation)"""
    id: UUID
    site_id: UUID
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int
    api_key: Optional[str] = None  # Only returned on creation


class APIKeyListResponse(BaseModel):
    """List of API keys (without actual keys)"""
    id: UUID
    site_id: UUID
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int


def generate_api_key() -> str:
    """Generate a secure random API key"""
    # Generate 32 random bytes (256 bits) and encode as hex
    random_bytes = secrets.token_bytes(32)
    key = random_bytes.hex()
    # Add 'sk-' prefix for easy identification
    return f"sk-{key}"


@router.post("", status_code=status.HTTP_201_CREATED, response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new API key for a site.

    The API key is returned ONCE during creation. Store it securely.

    Args:
        key_data: API key creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created API key with the actual key value

    Raises:
        HTTPException: 404 if site not found
    """
    # Verify site exists
    site = await db.get(Site, key_data.site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    # Generate API key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:8]  # First 8 chars for identification

    # Calculate expiration
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)

    # Create API key record
    api_key_obj = APIKey(
        site_id=key_data.site_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=key_data.name,
        scopes=key_data.scopes,
        expires_at=expires_at,
    )

    db.add(api_key_obj)
    await db.commit()
    await db.refresh(api_key_obj)

    # Return response with actual API key (only time it's returned)
    return APIKeyResponse(
        id=api_key_obj.id,
        site_id=api_key_obj.site_id,
        name=api_key_obj.name,
        key_prefix=api_key_obj.key_prefix,
        scopes=api_key_obj.scopes,
        is_active=api_key_obj.is_active,
        created_at=api_key_obj.created_at,
        expires_at=api_key_obj.expires_at,
        last_used_at=api_key_obj.last_used_at,
        usage_count=api_key_obj.usage_count,
        api_key=api_key,  # Only returned on creation!
    )


@router.get("/site/{site_id}", response_model=List[APIKeyListResponse])
async def list_api_keys_for_site(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all API keys for a site.

    Does not return the actual API key values, only metadata.

    Args:
        site_id: Site UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of API keys for the site
    """
    result = await db.execute(
        select(APIKey)
        .where(APIKey.site_id == site_id)
        .order_by(APIKey.created_at.desc())
    )
    api_keys = result.scalars().all()

    return [
        APIKeyListResponse(
            id=key.id,
            site_id=key.site_id,
            name=key.name,
            key_prefix=key.key_prefix,
            scopes=key.scopes,
            is_active=key.is_active,
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            usage_count=key.usage_count,
        )
        for key in api_keys
    ]


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Revoke an API key.

    Args:
        key_id: API key UUID
        reason: Optional reason for revocation
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message

    Raises:
        HTTPException: 404 if API key not found
    """
    api_key = await db.get(APIKey, key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Revoke the key
    api_key.is_active = False
    api_key.revoked_at = datetime.utcnow()
    api_key.revoked_reason = reason

    await db.commit()

    return {
        "message": "API key revoked successfully",
        "key_id": str(key_id),
        "revoked_at": api_key.revoked_at,
    }


@router.get("/{key_id}", response_model=APIKeyListResponse)
async def get_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get API key details by ID.

    Does not return the actual API key value.

    Args:
        key_id: API key UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        API key metadata

    Raises:
        HTTPException: 404 if API key not found
    """
    api_key = await db.get(APIKey, key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    return APIKeyListResponse(
        id=api_key.id,
        site_id=api_key.site_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        usage_count=api_key.usage_count,
    )
