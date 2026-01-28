#!/usr/bin/env python3
"""
Auto-fix Alembic migration files for common issues:
- Add pgvector import
- Add enum type creation for initial migrations
- Fix Vector usage
- Add create_type=False to enums
"""
import sys
from pathlib import Path
import re

def fix_migration_file(file_path: Path, is_initial: bool = False):
    """Fix common Alembic migration issues"""
    content = file_path.read_text()
    original = content
    
    # 1. Add pgvector import if Vector is used but not imported
    if 'Vector(' in content and 'from pgvector' not in content:
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
    
    # 3. For initial migrations, add setup code
    if is_initial and 'down_revision = None' in content:
        # Check if setup code already exists
        if 'CREATE EXTENSION IF NOT EXISTS vector' not in content:
            # Add setup code at the start of upgrade()
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
        
        # Add create_type=False to all enum columns
        content = re.sub(
            r"sa\.Enum\(([^)]+), name='(content_status|site_type_enum|plan_type_enum)'\)",
            r"sa.Enum(\1, name='\2', create_type=False)",
            content
        )
        
        # Add enum drops to downgrade
        if 'DROP TYPE IF EXISTS content_status' not in content:
            downgrade_code = '''    
    # Drop enum types (after all tables are dropped)
    op.execute("DROP TYPE IF EXISTS plan_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS site_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS content_status CASCADE;")
'''
            # Insert before "# ### end Alembic commands ###"
            content = re.sub(
                r'(\s+# ### end Alembic commands ###)',
                downgrade_code + r'\1',
                content
            )
    
    # Only write if changed
    if content != original:
        file_path.write_text(content)
        print(f"Fixed: {file_path.name}")
        return True
    else:
        print(f"  No changes needed: {file_path.name}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/fix_alembic_migration.py <migration_file> [--initial]")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    
    # Check if it's an initial migration
    if file_path.exists():
        content = file_path.read_text()
        is_initial = "--initial" in sys.argv or "down_revision = None" in content
    else:
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    if fix_migration_file(file_path, is_initial):
        sys.exit(0)
    else:
        sys.exit(0)  # Success even if no changes needed
