"""Main FastAPI application"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis import redis_client
from app.core.rate_limit import RateLimitMiddleware
from app.api.routes import auth_router, sites_router, pages_router, jobs_router, silos_router, onboarding_router, api_keys_router, scans_router
from app.api.routes.wordpress import router as wordpress_router
from app.queues.queue_manager import queue_manager
from app.api.exception_handlers import (
    governance_error_handler,
    validation_error_handler,
    publishing_error_handler,
    decommission_error_handler,
    cannibalization_error_handler,
    lifecycle_gate_error_handler,
    validation_exception_handler,
    integrity_error_handler,
)
from app.exceptions import (
    GovernanceError,
    ValidationError,
    PublishingError,
    DecommissionError,
    CannibalizationError,
    LifecycleGateError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Startup
    await redis_client.connect()
    await queue_manager.initialize()

    # Run Alembic migrations automatically (like Django's migrate)
    # This runs on every startup - Alembic tracks which migrations have been applied
    logger.info("Running Alembic database migrations...")
    try:
        from alembic import command
        from alembic.config import Config
        from pathlib import Path
        import os
        import time
        from sqlalchemy import pool
        
        # Get project root - DigitalOcean runs from project root, so use cwd first
        # Fall back to __file__-based path for local development
        cwd_root = Path(os.getcwd())
        file_based_root = Path(__file__).parent.parent.parent
        
        # Try current working directory first (production)
        project_root = cwd_root if (cwd_root / "alembic.ini").exists() else file_based_root
        
        alembic_ini_path = project_root / "alembic.ini"
        
        if not alembic_ini_path.exists():
            logger.warning(f"alembic.ini not found at {alembic_ini_path}")
            logger.warning(f"Current working directory: {os.getcwd()}")
            logger.warning(f"File-based root: {file_based_root}")
            logger.warning("Skipping migrations")
        else:
            logger.info(f"Found alembic.ini at {alembic_ini_path}")
            alembic_cfg = Config(str(alembic_ini_path))
            
            # Ensure we're in the project root directory for Alembic
            original_cwd = os.getcwd()
            try:
                os.chdir(str(project_root))
                logger.info("Starting migration upgrade to head...")
                start_time = time.time()
                
                # Run the migration with better logging
                logger.info("Executing Alembic upgrade command...")
                logger.info("This may take several minutes for initial schema creation...")
                
                # Check current state before migration
                try:
                    from sqlalchemy import create_engine, text
                    from app.core.config import settings
                    
                    sync_url = settings.database_url_sync
                    if sync_url.startswith('postgresql+asyncpg://'):
                        sync_url = sync_url.replace('postgresql+asyncpg://', 'postgresql://', 1)
                    
                    check_engine = create_engine(sync_url, poolclass=pool.NullPool)
                    with check_engine.connect() as conn:
                        # Count existing tables
                        result = conn.execute(text("""
                            SELECT COUNT(*) 
                            FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_type = 'BASE TABLE'
                        """))
                        table_count_before = result.scalar()
                        logger.info(f"Tables before migration: {table_count_before}")
                    check_engine.dispose()
                except Exception as check_err:
                    logger.warning(f"Could not check table count: {check_err}")
                
                # Configure Alembic to show more verbose output
                import logging as alembic_logging
                alembic_logger = alembic_logging.getLogger('alembic')
                alembic_logger.setLevel(logging.INFO)
                alembic_runtime_logger = alembic_logging.getLogger('alembic.runtime.migration')
                alembic_runtime_logger.setLevel(logging.INFO)
                
                try:
                    # Run upgrade with verbose output
                    logger.info("Starting migration execution (this may take 1-5 minutes)...")
                    command.upgrade(alembic_cfg, "head")
                    logger.info("✓ Alembic upgrade command completed successfully")
                    
                    # Check tables after migration
                    try:
                        check_engine = create_engine(sync_url, poolclass=pool.NullPool)
                        with check_engine.connect() as conn:
                            result = conn.execute(text("""
                                SELECT COUNT(*) 
                                FROM information_schema.tables 
                                WHERE table_schema = 'public' 
                                AND table_type = 'BASE TABLE'
                            """))
                            table_count_after = result.scalar()
                            logger.info(f"Tables after migration: {table_count_after}")
                            
                            # Check for critical tables
                            critical_tables = ['users', 'organizations', 'sites', 'pages']
                            for table in critical_tables:
                                result = conn.execute(text(f"""
                                    SELECT EXISTS (
                                        SELECT FROM information_schema.tables 
                                        WHERE table_schema = 'public' 
                                        AND table_name = '{table}'
                                    )
                                """))
                                exists = result.scalar()
                                status = "✓" if exists else "✗"
                                logger.info(f"  {status} Table '{table}': {'exists' if exists else 'MISSING'}")
                        check_engine.dispose()
                    except Exception as verify_err:
                        logger.warning(f"Could not verify tables: {verify_err}")
                except Exception as upgrade_error:
                    logger.error(f"Migration upgrade failed: {upgrade_error}")
                    logger.exception("Full upgrade error traceback:")
                    # Check if alembic_version table exists and what version it has
                    try:
                        from sqlalchemy import create_engine, text
                        from app.core.config import settings
                        
                        sync_url = settings.database_url_sync
                        if sync_url.startswith('postgresql+asyncpg://'):
                            sync_url = sync_url.replace('postgresql+asyncpg://', 'postgresql://', 1)
                        
                        engine = create_engine(sync_url, poolclass=pool.NullPool)
                        with engine.connect() as conn:
                            # Check if alembic_version exists
                            result = conn.execute(text("""
                                SELECT EXISTS (
                                    SELECT FROM information_schema.tables 
                                    WHERE table_schema = 'public' 
                                    AND table_name = 'alembic_version'
                                )
                            """))
                            version_table_exists = result.scalar()
                            
                            if version_table_exists:
                                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                                current_version = result.scalar()
                                logger.error(f"Current Alembic version in database: {current_version}")
                                logger.error("Migration may have partially completed. You may need to:")
                                logger.error("1. Check which tables exist")
                                logger.error("2. Manually fix alembic_version table")
                                logger.error("3. Or drop and re-run migrations")
                            else:
                                logger.error("alembic_version table does not exist - migration never completed")
                        
                        engine.dispose()
                    except Exception as check_error:
                        logger.error(f"Could not check migration status: {check_error}")
                    
                    raise
                
                elapsed_time = time.time() - start_time
                logger.info(f"Migration execution took {elapsed_time:.2f} seconds")
                
                # Verify migration completed by checking current revision
                try:
                    from alembic.script import ScriptDirectory
                    script = ScriptDirectory.from_config(alembic_cfg)
                    head_revision = script.get_current_head()
                    
                    # Check database version
                    from sqlalchemy import create_engine, text
                    from app.core.config import settings
                    
                    sync_url = settings.database_url_sync
                    if sync_url.startswith('postgresql+asyncpg://'):
                        sync_url = sync_url.replace('postgresql+asyncpg://', 'postgresql://', 1)
                    
                    engine = create_engine(sync_url, poolclass=pool.NullPool)
                    with engine.connect() as conn:
                        result = conn.execute(text("SELECT version_num FROM alembic_version"))
                        db_version = result.scalar()
                    
                    engine.dispose()
                    
                    if db_version:
                        logger.info(f"✓ Alembic migrations completed successfully in {elapsed_time:.2f} seconds")
                        logger.info(f"  Database is at revision: {db_version}")
                        logger.info(f"  Head revision is: {head_revision}")
                    else:
                        logger.warning("Migration completed but no version found in database")
                except Exception as verify_error:
                    # Migration ran, but verification failed - still log success
                    logger.info(f"✓ Alembic migrations completed in {elapsed_time:.2f} seconds")
                    logger.warning(f"Could not verify migration version: {verify_error}")
                
            except Exception as migration_error:
                elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
                logger.error(f"✗ Migration failed after {elapsed_time:.2f} seconds: {migration_error}")
                raise
            finally:
                os.chdir(original_cwd)
            
    except ImportError as e:
        logger.error(f"✗ Alembic not installed: {e}")
        logger.error("Please ensure 'alembic' is in requirements.txt and installed: pip install alembic")
    except Exception as e:
        logger.error(f"✗ Error running Alembic migrations: {e}")
        logger.exception("Full traceback:")
        # Don't fail startup, but log the error
    
    yield
    
    # Shutdown
    await queue_manager.close()
    await redis_client.disconnect()


app = FastAPI(
    title="Siloq - Governance-First AI SEO Platform",
    description="A governance engine for building structurally perfect websites",
    version="0.1.0",
    lifespan=lifespan,
)

# Add global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    """Handle all unhandled exceptions"""
    import logging
    logger = logging.getLogger(__name__)
    logger.exception(f"Unhandled exception in {request.url.path}: {type(exc).__name__}: {str(exc)}")
    
    from fastapi.responses import JSONResponse
    from fastapi import status
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": str(exc) if settings.environment != "production" else "Internal server error",
            },
            "path": str(request.url.path),
        },
    )

# CORS middleware - environment-aware configuration
def get_cors_origins() -> list:
    """Get CORS origins based on environment"""
    if settings.environment == "production":
        # In production, parse from comma-separated list or use specific domains
        origins = []
        if settings.cors_origins and settings.cors_origins != "*":
            # Normalize origins: remove trailing slashes
            origins = [origin.strip().rstrip('/') for origin in settings.cors_origins.split(",") if origin.strip()]
        
        # Always include the DigitalOcean dashboard origin (normalized - no trailing slash)
        required_origin = "https://siloq-dashboard-vcoj8.ondigitalocean.app"
        if required_origin not in origins:
            origins.append(required_origin)
        
        return origins if origins else [required_origin]
    else:
        # Development: allow all origins
        return ["*"]


"""Get CORS methods based on environment"""
def get_cors_methods() -> list:
    if settings.cors_allow_methods == "*":
        return ["*"]
    methods = [method.strip().upper() for method in settings.cors_allow_methods.split(",")]
    # Ensure OPTIONS is always included for preflight requests
    if "OPTIONS" not in methods:
        methods.append("OPTIONS")
    return methods


"""Get CORS headers based on environment"""
def get_cors_headers() -> list:
    if settings.cors_allow_headers == "*":
        return ["*"]
    headers = [header.strip() for header in settings.cors_allow_headers.split(",")]
    # Ensure common headers are included
    common_headers = ["Content-Type", "Authorization", "X-API-Key"]
    for header in common_headers:
        if header not in headers:
            headers.append(header)
    return headers


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=get_cors_methods(),
    allow_headers=get_cors_headers(),
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Register exception handlers
app.add_exception_handler(GovernanceError, governance_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(PublishingError, publishing_error_handler)
app.add_exception_handler(DecommissionError, decommission_error_handler)
app.add_exception_handler(CannibalizationError, cannibalization_error_handler)
app.add_exception_handler(LifecycleGateError, lifecycle_gate_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(sites_router, prefix="/api/v1")
app.include_router(pages_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(silos_router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(wordpress_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(scans_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Siloq",
        "version": "0.1.0",
        "description": "Governance-First AI SEO Platform",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint with actual connection testing.
    
    Returns:
        Health status with actual connection states
    """
    from sqlalchemy import text
    from app.core.redis import redis_client
    
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }
    
    # Test database connection
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"disconnected: {str(e)}"
        health_status["status"] = "degraded"
    
    # Test Redis connection
    try:
        client = await redis_client.get_client()
        await client.ping()
        health_status["redis"] = "connected"
    except Exception as e:
        health_status["redis"] = f"disconnected: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/api/v1/db-health")
async def database_health_check():
    """
    Database health check endpoint with detailed connection information.
    
    Returns:
        Detailed database connection status and configuration (masked)
    """
    import logging
    from sqlalchemy import text
    from urllib.parse import urlparse, urlunparse
    import time
    
    logger = logging.getLogger(__name__)
    
    def mask_url(url: str) -> str:
        """Mask sensitive parts of database URL"""
        try:
            parsed = urlparse(url)
            if parsed.password:
                masked = parsed._replace(password="***")
                return urlunparse(masked)
            return url
        except Exception:
            if len(url) > 20:
                return f"{url[:10]}...{url[-10:]}"
            return "***"
    
    result = {
        "status": "unknown",
        "async_database": {
            "url": mask_url(settings.database_url),
            "connected": False,
            "response_time_ms": None,
            "error": None,
        },
        "sync_database": {
            "url": mask_url(settings.database_url_sync),
            "configured": True,
        },
        "pool_status": {
            "size": None,
            "checked_in": None,
            "checked_out": None,
            "overflow": None,
        },
    }
    
    # Test async database connection
    logger.error("DB-HEALTH → Starting database connection test")
    logger.error(f"DB-HEALTH → Database URL (masked): {mask_url(settings.database_url)}")
    
    start_time = time.time()
    try:
        logger.error("DB-HEALTH → Attempting to get connection from pool...")
        async with engine.begin() as conn:
            logger.error("DB-HEALTH → Connection obtained, executing query...")
            # Test basic query
            query_result = await conn.execute(text("SELECT 1 as test, version() as pg_version"))
            row = query_result.first()
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            logger.error(f"DB-HEALTH → SUCCESS! Connected in {round(response_time, 2)}ms")
            result["async_database"]["connected"] = True
            result["async_database"]["response_time_ms"] = round(response_time, 2)
            result["async_database"]["postgres_version"] = row.pg_version if row else "unknown"
            result["status"] = "healthy"
            
    except TimeoutError as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"DB-HEALTH → TIMEOUT ERROR after {round(response_time, 2)}ms")
        logger.error(f"DB-HEALTH → TimeoutError: {str(e)}")
        logger.error(f"DB-HEALTH → Error type: {type(e).__name__}")
        logger.exception("DB-HEALTH → Full traceback:")
        result["async_database"]["connected"] = False
        result["async_database"]["response_time_ms"] = round(response_time, 2)
        result["async_database"]["error"] = f"TimeoutError: {str(e)}"
        result["status"] = "unhealthy"
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"DB-HEALTH → CONNECTION ERROR after {round(response_time, 2)}ms")
        logger.error(f"DB-HEALTH → Error: {str(e)}")
        logger.error(f"DB-HEALTH → Error type: {type(e).__name__}")
        logger.exception("DB-HEALTH → Full traceback:")
        result["async_database"]["connected"] = False
        result["async_database"]["response_time_ms"] = round(response_time, 2)
        result["async_database"]["error"] = f"{type(e).__name__}: {str(e)}"
        result["status"] = "unhealthy"
    
    # Get connection pool status
    try:
        pool = engine.pool
        result["pool_status"] = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception as e:
        result["pool_status"]["error"] = str(e)
    
    return result

