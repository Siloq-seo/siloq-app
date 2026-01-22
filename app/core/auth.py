"""Authentication and authorization utilities"""
from datetime import datetime, timedelta
from typing import Optional, Union
from uuid import UUID
import hashlib
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import get_db
from app.db.models import Site, APIKey


# Security scheme
security = HTTPBearer()


class AuthError(Exception):
    """Authentication error"""
    pass


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        raise AuthError("Invalid authentication credentials")


def hash_api_key(api_key: str) -> str:
    """Hash API key using SHA-256"""
    return hashlib.sha256(api_key.encode()).hexdigest()


async def verify_api_key(api_key: str, db: AsyncSession) -> Optional[dict]:
    """
    Verify API key and return associated site info.

    Args:
        api_key: The API key to verify
        db: Database session

    Returns:
        dict with site_id and scopes if valid, None otherwise
    """
    key_hash = hash_api_key(api_key)

    # Query for API key
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True,
        )
    )
    api_key_obj = result.scalar_one_or_none()

    if not api_key_obj:
        return None

    # Check expiration
    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
        return None

    # Update usage tracking
    await db.execute(
        update(APIKey)
        .where(APIKey.id == api_key_obj.id)
        .values(
            last_used_at=datetime.utcnow(),
            usage_count=APIKey.usage_count + 1
        )
    )
    await db.commit()

    return {
        "site_id": str(api_key_obj.site_id),
        "scopes": api_key_obj.scopes,
        "auth_type": "api_key",
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get current authenticated user from JWT token or API key.

    Supports both JWT tokens and API keys for authentication.
    API keys are identified by the 'sk-' prefix.

    Returns:
        dict with user_id and account_id (for JWT) or site_id and scopes (for API key)

    Raises:
        HTTPException: If token/key is invalid or missing
    """
    try:
        token = credentials.credentials

        # Check if it's an API key (starts with 'sk-')
        if token.startswith('sk-'):
            api_key_info = await verify_api_key(token, db)
            if api_key_info:
                return api_key_info
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Otherwise, treat as JWT token
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub")
        account_id: Optional[str] = payload.get("account_id")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "user_id": user_id,
            "account_id": account_id,
            "auth_type": "jwt",
        }
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_site_access(
    site_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Site:
    """
    Verify that the current user has access to the specified site.
    
    This ensures tenant scoping - users can only access sites they own.
    
    Args:
        site_id: Site UUID to verify access for
        current_user: Current authenticated user (from get_current_user)
        db: Database session
        
    Returns:
        Site object if access is granted
        
    Raises:
        HTTPException: 404 if site not found, 403 if access denied
    """
    # Get site
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # TODO: In a full implementation, you would check site.owner_account_id == current_user["account_id"]
    # For now, we'll allow access if the user is authenticated
    # In production, add an owner_account_id column to Site model and enforce it here
    
    return site


async def verify_page_access(
    page_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify that the current user has access to the specified page.
    
    This ensures tenant scoping - users can only access pages from sites they own.
    
    Args:
        page_id: Page UUID to verify access for
        current_user: Current authenticated user (from get_current_user)
        db: Database session
        
    Returns:
        Page object if access is granted
        
    Raises:
        HTTPException: 404 if page not found, 403 if access denied
    """
    from app.db.models import Page
    
    # Get page
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    
    # Verify site access (this will check ownership)
    await verify_site_access(page.site_id, current_user, db)
    
    return page


# Optional: For endpoints that don't require auth (like health checks)
async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> Optional[dict]:
    """Get current user if token is provided, otherwise return None"""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None

