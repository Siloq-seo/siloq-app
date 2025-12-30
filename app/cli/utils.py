"""Utility functions for CLI commands"""
import os
from typing import Optional, Tuple
from urllib.parse import urlparse

import psycopg2
from psycopg2.extensions import connection, ISOLATION_LEVEL_AUTOCOMMIT

# Try to import settings, but handle gracefully if not available
_settings = None
try:
    from app.core.config import settings as _settings
except Exception:
    pass


def parse_database_url(db_url: str) -> Tuple[str, str, str, int, str]:
    """
    Parse PostgreSQL database URL into connection components.
    
    Args:
        db_url: Database URL in format postgresql://user:pass@host:port/dbname
        
    Returns:
        Tuple of (user, password, host, port, database)
    """
    parsed = urlparse(db_url)
    user = parsed.username or os.getenv("POSTGRES_USER", "postgres")
    password = parsed.password or os.getenv("POSTGRES_PASSWORD", "postgres")
    host = parsed.hostname or os.getenv("DB_HOST", "localhost")
    port = parsed.port or int(os.getenv("DB_PORT", "5432"))
    database = parsed.path.lstrip("/")
    
    return user, password, host, port, database


def get_database_connection_params(dbname: str = "postgres") -> Tuple[str, str, str, int, str]:
    """
    Get database connection parameters from settings or environment.
    
    Args:
        dbname: Database name to connect to
        
    Returns:
        Tuple of (user, password, host, port, database)
    """
    db_url = ""
    if _settings and hasattr(_settings, "database_url_sync"):
        db_url = _settings.database_url_sync
    else:
        db_url = os.getenv("DATABASE_URL_SYNC", "")
    
    if db_url and db_url.startswith("postgresql://"):
        user, password, host, port, _ = parse_database_url(db_url)
        database = dbname if dbname != "postgres" else _
        return user, password, host, port, database
    
    # Fallback to environment variables
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    database = dbname
    
    return user, password, host, port, database


def get_db_connection(dbname: str = "postgres") -> connection:
    """
    Create and return a PostgreSQL database connection.
    
    Args:
        dbname: Name of the database to connect to
        
    Returns:
        psycopg2 connection object
        
    Raises:
        psycopg2.Error: If connection fails
    """
    user, password, host, port, database = get_database_connection_params(dbname)
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        return conn
    except psycopg2.Error as e:
        raise ConnectionError(
            f"Failed to connect to database {database} at {host}:{port}: {e}"
        ) from e

