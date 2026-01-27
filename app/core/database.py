"""Database connection and session management"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from app.core.config import settings

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
        # asyncpg accepts: True (for SSL required), False (for no SSL), or SSL context object
        if sslmode in ['require', 'prefer', 'verify-ca', 'verify-full']:
            # For asyncpg, use True for SSL required (most common case)
            # For verify-ca/verify-full, we'd need SSL context, but True works for most cases
            connect_args['ssl'] = True
        elif sslmode == 'disable':
            connect_args['ssl'] = False
        else:
            # Default to True for security (SSL required)
            connect_args['ssl'] = True
    
    # Rebuild query string without sslmode
    new_query = urlencode(query_params, doseq=True)
    
    # Rebuild URL
    new_parsed = parsed._replace(query=new_query)
    database_url = urlunparse(new_parsed)
    
    # Convert to asyncpg URL
    if database_url.startswith('postgresql://') and '+asyncpg' not in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)

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

