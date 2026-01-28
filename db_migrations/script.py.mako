"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
${imports if imports else ""}
# Auto-import pgvector if Vector is used
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    pass

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
% if down_revision is None:
    # Initial migration setup: extensions and enum types
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # Drop types if they exist (for clean start)
    op.execute("DROP TYPE IF EXISTS plan_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS site_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS content_status CASCADE;")
    # Create enum types (idempotent - won't fail if already exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE content_status AS ENUM ('draft', 'pending_review', 'approved', 'published', 'decommissioned', 'blocked');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE site_type_enum AS ENUM ('LOCAL_SERVICE', 'ECOMMERCE');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE plan_type_enum AS ENUM ('trial', 'blueprint', 'operator', 'agency', 'empire');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    
% endif
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
% if down_revision is None:
    # Drop enum types for initial migration
    op.execute("DROP TYPE IF EXISTS plan_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS site_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS content_status CASCADE;")
% endif