"""Database migration runner - runs all SQL migrations automatically"""
import logging
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def run_all_migrations(engine: AsyncEngine) -> bool:
    """
    Run all database migrations in order (similar to Django's migrate).
    
    Args:
        engine: SQLAlchemy async engine
        
    Returns:
        True if all migrations succeeded, False otherwise
    """
    # Get migrations directory
    project_root = Path(__file__).parent.parent.parent
    migrations_dir = project_root / "migrations"
    
    if not migrations_dir.exists():
        logger.warning(f"Migrations directory not found: {migrations_dir}")
        return False
    
    # Get all migration files in order (V001, V002, etc.)
    migration_files = sorted(
        [
            f
            for f in migrations_dir.glob("V*.sql")
            if f.name.startswith("V") and not f.name.startswith("V__")
        ]
    )
    
    if not migration_files:
        logger.warning("No migration files found")
        return False
    
    logger.info(f"Found {len(migration_files)} migration files to run")
    
    try:
        async with engine.begin() as conn:
            for migration_file in migration_files:
                logger.info(f"Running migration: {migration_file.name}...")
                
                try:
                    # Read SQL file
                    sql_content = migration_file.read_text(encoding="utf-8")
                    
                    # Split by semicolon and execute each statement
                    # Filter out empty statements and comments
                    statements = [
                        s.strip() 
                        for s in sql_content.split(';') 
                        if s.strip() and not s.strip().startswith('--')
                    ]
                    
                    for statement in statements:
                        if statement:
                            await conn.execute(text(statement))
                    
                    logger.info(f"✓ Migration completed: {migration_file.name}")
                    
                except Exception as e:
                    logger.error(f"✗ Migration failed: {migration_file.name} - {e}")
                    # Check if it's a "already exists" error (idempotent migrations)
                    error_str = str(e).lower()
                    if "already exists" in error_str or "duplicate" in error_str:
                        logger.warning(f"  (Migration may have already been applied: {migration_file.name})")
                        continue
                    raise
        
        logger.info("✓ All migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration execution failed: {e}")
        logger.exception("Full traceback:")
        return False
