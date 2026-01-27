"""Database connection and session management"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import ssl
import logging
from app.core.config import settings

# Setup logger
logger = logging.getLogger(__name__)

# Log database URLs (masked for security)
def mask_url(url: str) -> str:
    """Mask sensitive parts of database URL for logging"""
    try:
        parsed = urlparse(url)
        if parsed.password:
            # Replace password with ***
            masked = parsed._replace(password="***")
            return urlunparse(masked)
        return url
    except Exception:
        # If parsing fails, just show first/last few chars
        if len(url) > 20:
            return f"{url[:10]}...{url[-10:]}"
        return "***"

# Log original database URLs
logger.info("=" * 80)
logger.info("DATABASE CONFIGURATION")
logger.info("=" * 80)
logger.info(f"DATABASE_URL (async): {mask_url(settings.database_url)}")
logger.info(f"DATABASE_URL_SYNC: {mask_url(settings.database_url_sync)}")
logger.info("=" * 80)

# Ensure database_url uses asyncpg driver for async operations
# Digital Ocean and other platforms may inject postgresql:// URLs with sslmode
database_url = settings.database_url
connect_args = {}

# Parse URL to handle sslmode parameter (asyncpg doesn't support sslmode in URL, needs ssl in connect_args)
if database_url.startswith('postgresql://') or database_url.startswith('postgresql+asyncpg://'):
    # Parse the URL
    parsed = urlparse(database_url)
    query_params = parse_qs(parsed.query)
    
    # Check if sslmode is present
    sslmode = None
    if 'sslmode' in query_params:
        sslmode = query_params['sslmode'][0]
        # Remove sslmode from query params (asyncpg doesn't support it in URL)
        del query_params['sslmode']
        
        # Convert sslmode to asyncpg's ssl parameter format
        # For DigitalOcean managed databases, use SSL context that doesn't verify certificates
        if sslmode in ['require', 'prefer']:
            # Create SSL context that requires SSL but doesn't verify certificate
            # This is common for managed database services
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connect_args['ssl'] = ssl_context
        elif sslmode in ['verify-ca', 'verify-full']:
            # For verify-ca/verify-full, use default SSL context with verification
            connect_args['ssl'] = ssl.create_default_context()
        elif sslmode == 'disable':
            connect_args['ssl'] = False
        else:
            # Default: create SSL context without verification (for managed databases)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connect_args['ssl'] = ssl_context
    
    # Rebuild query string without sslmode
    new_query = urlencode(query_params, doseq=True)
    
    # Rebuild URL
    new_parsed = parsed._replace(query=new_query)
    database_url = urlunparse(new_parsed)
    
    # Convert to asyncpg URL
    if database_url.startswith('postgresql://') and '+asyncpg' not in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)

# Add connection timeout to connect_args if SSL is enabled
if 'ssl' in connect_args and connect_args['ssl']:
    # Set connection timeout (in seconds) for asyncpg
    connect_args['timeout'] = 10  # 10 second connection timeout
    logger.info("SSL enabled for database connection")
else:
    logger.info("SSL disabled for database connection")

# Log final database URL (masked)
logger.info(f"Final DATABASE_URL (after processing): {mask_url(database_url)}")
logger.info(f"Connect args: ssl={'enabled' if 'ssl' in connect_args else 'disabled'}, timeout={connect_args.get('timeout', 'default')}")

# Create async engine with connection pool settings
engine = create_async_engine(
    database_url,
    echo=settings.environment == "development",
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_size=5,  # Number of connections to maintain
    max_overflow=10,  # Maximum overflow connections
    pool_timeout=30,  # Timeout for getting connection from pool
)

logger.info("Database engine created successfully")
logger.info("=" * 80)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

