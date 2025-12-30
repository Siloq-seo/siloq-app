"""Database management commands for Siloq CLI."""
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, List

import click
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from app.cli.utils import get_db_connection


@contextmanager
def db_connection(dbname: str = "postgres") -> Iterator[Any]:
    """
    Context manager for database connections.
    
    Args:
        dbname: Database name to connect to
        
    Yields:
        Database connection object
        
    Example:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
    """
    conn = get_db_connection(dbname)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        yield conn
    finally:
        conn.close()


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def get_migrations_dir() -> Path:
    """Get the migrations directory path."""
    return get_project_root() / "migrations"


@click.group()
def db_group() -> None:
    """Database management commands."""
    pass


@db_group.command()
def migrate() -> None:
    """Run all database migrations."""
    click.echo(click.style("Running migrations...", fg="yellow"))
    run_migrations()


@db_group.command()
def patch_1_3_1() -> None:
    """Apply v1.3.1 patches to the database."""
    click.echo(click.style("Applying v1.3.1 patches...", fg="yellow"))
    
    migrations_dir = get_migrations_dir()
    patches = [
        "V002__silo_decay_trigger.sql",
        "V003__constraint_enforcement.sql",
    ]
    
    with db_connection() as conn:
        cur = conn.cursor()
        
        for patch_file in patches:
            patch_path = migrations_dir / patch_file
            if not patch_path.exists():
                click.echo(
                    click.style(f"Warning: {patch_file} not found", fg="yellow")
                )
                continue
            
            click.echo(f"  Applying {patch_file}...")
            try:
                with open(patch_path, "r", encoding="utf-8") as f:
                    cur.execute(f.read())
            except Exception as e:
                click.echo(
                    click.style(f"    ✗ Error applying {patch_file}: {e}", fg="red")
                )
                raise
        
        cur.close()
    
    click.echo(click.style("✓ Patches applied", fg="green"))


@db_group.command()
def verify() -> None:
    """Test all database constraints."""
    click.echo(click.style("Verifying constraints...", fg="yellow"))
    from app.cli.test import run_all_tests
    
    run_all_tests()


@db_group.command()
def bootstrap() -> None:
    """Initialize local development environment."""
    click.echo(
        click.style("Bootstrapping local development environment...", fg="yellow")
    )
    
    project_root = get_project_root()
    bootstrap_script = project_root / "scripts" / "bootstrap-db.sh"
    
    if not bootstrap_script.exists():
        click.echo(
            click.style(
                f"Error: Bootstrap script not found: {bootstrap_script}",
                fg="red",
            )
        )
        return
    
    # Ensure script is executable
    os.chmod(bootstrap_script, 0o755)
    
    result = subprocess.run(
        [str(bootstrap_script)],
        cwd=project_root,
        check=False,
    )
    
    if result.returncode == 0:
        click.echo(click.style("✓ Bootstrap complete", fg="green"))
    else:
        click.echo(click.style("✗ Bootstrap failed", fg="red"))
        raise click.Abort()


@db_group.command()
def seed() -> None:
    """Seed database with test data."""
    click.echo(click.style("Seeding test data...", fg="yellow"))
    seed_test_data()


@db_group.command()
def reset() -> None:
    """Reset database (drop all tables and recreate)."""
    click.echo(click.style("Resetting database...", fg="yellow"))
    reset_database()


def reset_database() -> None:
    """Reset database by dropping and recreating it."""
    with db_connection() as conn:
        cur = conn.cursor()
        
        # Get current database name
        cur.execute("SELECT current_database()")
        dbname = cur.fetchone()[0]
        cur.close()
    
    # Connect to postgres database to drop/recreate
    with db_connection("postgres") as conn:
        cur = conn.cursor()
        
        # Terminate existing connections to target database
        cur.execute(
            sql.SQL(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()"
            ),
            [dbname],
        )
        
        # Drop and recreate database
        cur.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
        )
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
        
        cur.close()
    
    click.echo(click.style("✓ Database reset complete", fg="green"))


def run_migrations() -> None:
    """Run all database migrations in order."""
    migrations_dir = get_migrations_dir()
    
    # Get migration files in order (V001, V002, etc.)
    migration_files = sorted(
        [
            f
            for f in migrations_dir.glob("V*.sql")
            if f.name.startswith("V") and not f.name.startswith("V__")
        ]
    )
    
    if not migration_files:
        click.echo(click.style("No migration files found", fg="yellow"))
        return
    
    with db_connection() as conn:
        cur = conn.cursor()
        
        for migration_file in migration_files:
            click.echo(f"  Running {migration_file.name}...")
            try:
                with open(migration_file, "r", encoding="utf-8") as f:
                    cur.execute(f.read())
                click.echo(
                    click.style(f"    ✓ {migration_file.name}", fg="green")
                )
            except Exception as e:
                click.echo(
                    click.style(
                        f"    ✗ {migration_file.name}: {e}",
                        fg="red",
                    )
                )
                cur.close()
                raise
        
        cur.close()
    
    click.echo(click.style("✓ All migrations complete", fg="green"))


def seed_test_data() -> None:
    """Seed database with test data from seed file."""
    migrations_dir = get_migrations_dir()
    seed_file = migrations_dir / "seed_test_data.sql"
    
    if not seed_file.exists():
        click.echo(
            click.style("Warning: Test data seed file not found", fg="yellow")
        )
        return
    
    with db_connection() as conn:
        cur = conn.cursor()
        
        click.echo("  Seeding test data...")
        try:
            with open(seed_file, "r", encoding="utf-8") as f:
                cur.execute(f.read())
            click.echo(click.style("✓ Test data seeded", fg="green"))
        except Exception as e:
            click.echo(
                click.style(f"✗ Error seeding test data: {e}", fg="red")
            )
            raise
        finally:
            cur.close()
