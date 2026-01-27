"""Authentication routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
from passlib.context import CryptContext

from app.core.database import get_db
from app.core.auth import create_access_token, get_current_user
from app.db.models import User


# aplied logger for the debugging 
import logging
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/auth", tags=["auth"])

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str
    name: str


class RegisterResponse(BaseModel):
    """User registration response"""
    success: bool
    message: str
    user_id: Optional[str] = None
    access_token: Optional[str] = None


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """User login response"""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    name: Optional[str] = None


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterResponse,
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    logger.info("REGISTER → STEP 1: Request received")
    logger.info(f"Payload email={request.email}")

    try:
        logger.info("REGISTER → STEP 2: Checking existing user")
        result = await db.execute(
            select(User).where(
                User.email == request.email.lower(),
                User.deleted_at.is_(None)
            )
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.warning("REGISTER → Email already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        logger.info("REGISTER → STEP 3: Validating password")
        if len(request.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters",
            )

        logger.info("REGISTER → STEP 4: Hashing password")
        password_hash = hash_password(request.password)

        logger.info("REGISTER → STEP 5: Creating user object")
        user = User(
            email=request.email.lower(),
            password_hash=password_hash,
            name=request.name,
            role="viewer",
        )

        db.add(user)

        logger.info("REGISTER → STEP 6: Committing to database")
        await db.commit()
        await db.refresh(user)

        logger.info(f"REGISTER → STEP 7: User created id={user.id}")

        logger.info("REGISTER → STEP 8: Creating access token")
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "account_id": (
                    str(user.organization_id)
                    if user.organization_id
                    else None
                ),
            }
        )

        logger.info("REGISTER → SUCCESS")
        return RegisterResponse(
            success=True,
            message="User registered successfully",
            user_id=str(user.id),
            access_token=access_token,
        )

    except HTTPException:
        raise

    except TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable"
        )


    except Exception as e:
        logger.exception("REGISTER → UNEXPECTED ERROR")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.
    
    Args:
        request: Login credentials (email, password)
        db: Database session
        
    Returns:
        Login response with access token
        
    Raises:
        HTTPException: 401 if credentials are invalid
    """
    # Find user
    result = await db.execute(
        select(User).where(User.email == request.email.lower(), User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user has a password (OAuth users might not)
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    await db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "account_id": str(user.organization_id) if user.organization_id else None}
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=str(user.id),
        email=user.email,
        name=user.name,
    )


@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user (from dependency)
        db: Database session
        
    Returns:
        User information
    """
    if current_user.get("auth_type") == "api_key":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint requires user authentication, not API key"
        )
    
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user"
        )
    
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
