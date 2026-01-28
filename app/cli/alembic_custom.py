"""Custom Alembic commands that auto-fix generated migrations"""
import click
from pathlib import Path
import re
import subprocess
import sys


def find_latest_migration():
    """Find the most recently created migration file"""
    versions_dir = Path("db_migrations/versions")
    if not versions_dir.exists():
        return None
    
    migration_files = list(versions_dir.glob("*.py"))
    if not migration_files:
        return None
    
    # Sort by modification time, newest first
    return max(migration_files, key=lambda p: p.stat().st_mtime)


def auto_fix_migration(file_path: Path):
    """Automatically fix common Alembic migration issues"""
    content = file_path.read_text()
    original = content
    is_initial = "down_revision = None" in content
    
    # 1. Add pgvector import if Vector is used
    if 'Vector(' in content or 'pgvector' in content:
        if 'from pgvector.sqlalchemy import Vector' not in content:
            # Add import after sqlalchemy imports
            content = re.sub(
                r'(from sqlalchemy\.dialects import postgresql)',
                r'\1\nfrom pgvector.sqlalchemy import Vector',
                content
            )
    
    # 2. Fix Vector usage (pgvector.sqlalchemy.vector.VECTOR -> Vector)
    content = re.sub(
        r'pgvector\.sqlalchemy\.vector\.VECTOR\(dim=(\d+)\)',
        r'Vector(\1)',
        content
    )
    
    # 3. For initial migrations, ensure setup code exists
    if is_initial:
        # Check if setup code already exists (from template)
        if 'CREATE EXTENSION IF NOT EXISTS vector' not in content:
            setup_code = '''    # Create pgvector extension first (if not exists)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # Drop existing enum types if they exist (clean start)
    op.execute("DROP TYPE IF EXISTS plan_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS site_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS content_status CASCADE;")
    
    # Create PostgreSQL enum types fresh (before tables that use them)
    op.execute("CREATE TYPE content_status AS ENUM ('draft', 'pending_review', 'approved', 'published', 'decommissioned', 'blocked');")
    op.execute("CREATE TYPE site_type_enum AS ENUM ('LOCAL_SERVICE', 'ECOMMERCE');")
    op.execute("CREATE TYPE plan_type_enum AS ENUM ('trial', 'blueprint', 'operator', 'agency', 'empire');")
    
    '''
            
            # Insert after "def upgrade() -> None:"
            content = re.sub(
                r'(def upgrade\(\) -> None:\s*\n)',
                r'\1' + setup_code,
                content,
                count=1
            )
        
        # Add create_type=False to all enum columns (critical fix)
        content = re.sub(
            r"sa\.Enum\(([^)]+), name='(content_status|site_type_enum|plan_type_enum)'\)(?!\s*,\s*create_type)",
            r"sa.Enum(\1, name='\2', create_type=False)",
            content
        )
        
        # Also fix if create_type is already there but True
        content = re.sub(
            r"sa\.Enum\(([^)]+), name='(content_status|site_type_enum|plan_type_enum)', create_type=True\)",
            r"sa.Enum(\1, name='\2', create_type=False)",
            content
        )
        
        # Add enum drops to downgrade if not present
        if 'DROP TYPE IF EXISTS content_status' not in content or 'def downgrade' in content:
            downgrade_code = '''    
    # Drop enum types (after all tables are dropped)
    op.execute("DROP TYPE IF EXISTS plan_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS site_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS content_status CASCADE;")
'''
            # Insert before "# ### end Alembic commands ###" or at end of downgrade
            if '# ### end Alembic commands ###' in content:
                content = re.sub(
                    r'(\s+# ### end Alembic commands ###)',
                    downgrade_code + r'\1',
                    content
                )
            else:
                # Add at end of downgrade function
                content = re.sub(
                    r'(def downgrade\(\) -> None:\s*\n\s+[^\n]+\n)(\s+)([^\s])',
                    r'\1\2' + downgrade_code.strip() + '\n\2\3',
                    content,
                    count=1
                )
    
    # Only write if changed
    if content != original:
        file_path.write_text(content)
        return True
    return False


@click.command()
@click.argument('message')
def generate_migration(message: str):
    """Generate Alembic migration with auto-fixes applied"""
    click.echo(f"Generating migration: {message}")
    
    # Run alembic revision --autogenerate
    result = subprocess.run(
        ['alembic', 'revision', '--autogenerate', '-m', message],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        click.echo(f"Error generating migration: {result.stderr}", err=True)
        sys.exit(1)
    
    # Find the latest migration file
    migration_file = find_latest_migration()
    if not migration_file:
        click.echo("Error: Could not find generated migration file", err=True)
        sys.exit(1)
    
    click.echo(f"Found migration: {migration_file.name}")
    
    # Auto-fix the migration
    if auto_fix_migration(migration_file):
        click.echo(f"✓ Auto-fixed: {migration_file.name}")
    else:
        click.echo(f"  No fixes needed: {migration_file.name}")
    
    click.echo(f"\n✓ Migration ready: {migration_file}")
    click.echo("Run: alembic upgrade head")


if __name__ == '__main__':
    generate_migration()
