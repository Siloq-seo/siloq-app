"""Initial schema with V2 dormant fields

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable required extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    
    # Create content_status enum
    content_status_enum = postgresql.ENUM(
        'draft', 'pending_review', 'approved', 'published', 'decommissioned', 'blocked',
        name='content_status',
        create_type=True
    )
    content_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create site_type enum
    site_type_enum = postgresql.ENUM(
        'LOCAL_SERVICE', 'ECOMMERCE',
        name='site_type_enum',
        create_type=True
    )
    site_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create sites table
    op.create_table(
        'sites',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('domain', sa.String(), unique=True, nullable=False),
        sa.Column('site_type', site_type_enum, nullable=True),
        sa.Column('geo_coordinates', postgresql.JSONB, nullable=True),
        sa.Column('service_area', postgresql.JSONB, nullable=True),
        sa.Column('product_sku_pattern', sa.String(), nullable=True),
        sa.Column('currency_settings', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('length(trim(name)) > 0', name='chk_site_name_not_empty'),
        sa.CheckConstraint('length(trim(domain)) > 0', name='chk_site_domain_not_empty'),
    )
    
    # Create pages table with normalized_path and V2 fields
    op.create_table(
        'pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        # normalized_path is a generated column - handled via raw SQL
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('is_proposal', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', content_status_enum, nullable=False, server_default='draft'),
        sa.Column('authority_score', sa.Float(), server_default='0.0'),
        sa.Column('source_urls', postgresql.JSONB, server_default='[]'),
        sa.Column('governance_checks', postgresql.JSONB, server_default='{}'),
        # V2 Dormant Fields
        sa.Column('v2_governance', postgresql.JSONB, nullable=False, server_default='{"signal_status": "IDLE", "enforcement_log": []}'),
        sa.Column('active_widget_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('widget_config_payload', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decommissioned_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('length(trim(path)) > 0', name='chk_page_path_not_empty'),
        sa.CheckConstraint('length(trim(title)) > 0', name='chk_page_title_not_empty'),
        sa.CheckConstraint('authority_score >= 0.0 AND authority_score <= 1.0', name='chk_authority_score_range'),
        sa.UniqueConstraint('site_id', 'normalized_path', name='uniq_page_normalized_path_per_site'),
    )
    
    # Add normalized_path as generated column (must be done after table creation)
    op.execute("""
        ALTER TABLE pages 
        ADD COLUMN IF NOT EXISTS normalized_path TEXT 
        GENERATED ALWAYS AS (lower(trim(path))) STORED;
    """)
    
    # Create indexes for pages
    op.create_index('idx_pages_site_id', 'pages', ['site_id'])
    op.create_index('idx_pages_normalized_path', 'pages', ['normalized_path'])
    op.create_index('idx_pages_status', 'pages', ['status'])
    op.create_index('idx_pages_is_proposal', 'pages', ['is_proposal'])
    
    # Create keywords table
    op.create_table(
        'keywords',
        sa.Column('keyword', sa.Text(), primary_key=True),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint('length(trim(keyword)) > 0', name='chk_keyword_not_empty'),
        sa.CheckConstraint('keyword = lower(trim(keyword))', name='chk_keyword_normalized'),
    )
    op.create_index('idx_keywords_page_id', 'keywords', ['page_id'])
    
    # Create silos table
    op.create_table(
        'silos',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('is_finalized', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('parent_silo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('silos.id', ondelete='SET NULL'), nullable=True),
        sa.Column('authority_funnel_score', sa.Float(), server_default='0.0'),
        sa.Column('anchor_governance_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('length(trim(name)) > 0', name='chk_silo_name_not_empty'),
        sa.CheckConstraint('length(trim(slug)) > 0', name='chk_silo_slug_not_empty'),
        sa.CheckConstraint('position >= 1 AND position <= 7', name='chk_silo_position_range'),
        sa.CheckConstraint('authority_funnel_score >= 0.0 AND authority_funnel_score <= 1.0', name='chk_authority_funnel_score_range'),
        sa.UniqueConstraint('site_id', 'position', name='uniq_silo_position_per_site'),
        sa.UniqueConstraint('site_id', 'slug', name='uniq_silo_slug_per_site'),
    )
    op.create_index('idx_silos_site_id', 'silos', ['site_id'])
    op.create_index('idx_silos_position', 'silos', ['site_id', 'position'])
    op.create_index('idx_silos_is_finalized', 'silos', ['is_finalized'])
    op.create_index('idx_silos_parent_silo_id', 'silos', ['parent_silo_id'])
    
    # Create page_silos table
    op.create_table(
        'page_silos',
        sa.Column('page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('silo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('silos.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('is_supporting_page', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('supporting_role', sa.String(), nullable=True),
        sa.Column('authority_weight', sa.Float(), server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint('authority_weight >= 0.0 AND authority_weight <= 2.0', name='chk_authority_weight_range'),
    )
    op.create_index('idx_page_silos_is_supporting', 'page_silos', ['is_supporting_page'])
    
    # Create system_events table
    op.create_table(
        'system_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('payload', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint('length(trim(event_type)) > 0', name='chk_event_type_not_empty'),
        sa.CheckConstraint('length(trim(entity_type)) > 0', name='chk_entity_type_not_empty'),
    )
    op.create_index('idx_system_events_entity', 'system_events', ['entity_type', 'entity_id'])
    op.create_index('idx_system_events_created_at', 'system_events', ['created_at'])
    op.create_index('idx_system_events_type', 'system_events', ['event_type'])
    
    # Create cannibalization_checks table
    op.create_table(
        'cannibalization_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('compared_with_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=False),
        sa.Column('threshold_exceeded', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint('similarity_score >= 0.0 AND similarity_score <= 1.0', name='chk_similarity_score_range'),
        sa.CheckConstraint('page_id != compared_with_id', name='chk_no_self_comparison'),
    )
    op.create_index('idx_cannibalization_page_id', 'cannibalization_checks', ['page_id'])
    op.create_index('idx_cannibalization_compared_with', 'cannibalization_checks', ['compared_with_id'])
    op.create_index('idx_cannibalization_created_at', 'cannibalization_checks', ['created_at'])
    
    # Create clusters table
    op.create_table(
        'clusters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('length(trim(name)) > 0', name='chk_cluster_name_not_empty'),
        sa.UniqueConstraint('site_id', 'name', name='uniq_cluster_name_per_site'),
    )
    op.create_index('idx_clusters_site_id', 'clusters', ['site_id'])
    
    # Create cluster_pages table
    op.create_table(
        'cluster_pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('cluster_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(), nullable=False, server_default='member'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('member', 'anchor', 'hub')", name='chk_cluster_page_role_valid'),
        sa.UniqueConstraint('cluster_id', 'page_id', name='uniq_cluster_page'),
    )
    op.create_index('idx_cluster_pages_cluster_id', 'cluster_pages', ['cluster_id'])
    op.create_index('idx_cluster_pages_page_id', 'cluster_pages', ['page_id'])
    
    # Create anchor_links table
    op.create_table(
        'anchor_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('from_page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('to_page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('anchor_text', sa.String(), nullable=False),
        sa.Column('silo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('silos.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_internal', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('authority_passed', sa.Float(), server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint('length(trim(anchor_text)) > 0', name='chk_anchor_text_not_empty'),
        sa.CheckConstraint('from_page_id != to_page_id', name='chk_no_self_link'),
        sa.CheckConstraint('authority_passed >= 0.0 AND authority_passed <= 1.0', name='chk_authority_passed_range'),
        sa.UniqueConstraint('from_page_id', 'to_page_id', 'anchor_text', name='uniq_anchor_link'),
    )
    op.create_index('idx_anchor_links_from_page', 'anchor_links', ['from_page_id'])
    op.create_index('idx_anchor_links_to_page', 'anchor_links', ['to_page_id'])
    op.create_index('idx_anchor_links_silo_id', 'anchor_links', ['silo_id'])
    
    # Create generation_jobs table
    op.create_table(
        'generation_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', sa.String(), unique=True, nullable=False),
        sa.Column('status', sa.String(50), server_default='draft'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('total_cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('structured_output_metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('state_transition_history', postgresql.JSONB, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('preflight_approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('prompt_locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'preflight_approved', 'prompt_locked', 'processing', 'postcheck_passed', 'postcheck_failed', 'completed', 'failed', 'ai_max_retry_exceeded')",
            name='chk_job_status_valid'
        ),
        sa.CheckConstraint('length(trim(job_id)) > 0', name='chk_job_id_not_empty'),
        sa.CheckConstraint('retry_count >= 0', name='chk_retry_count_non_negative'),
        sa.CheckConstraint('max_retries > 0', name='chk_max_retries_positive'),
        sa.CheckConstraint('total_cost_usd >= 0.0', name='chk_total_cost_non_negative'),
    )
    op.create_index('idx_generation_jobs_page_id', 'generation_jobs', ['page_id'])
    op.create_index('idx_generation_jobs_status', 'generation_jobs', ['status'])
    op.create_index('idx_generation_jobs_job_id', 'generation_jobs', ['job_id'])
    op.create_index('idx_generation_jobs_retry_count', 'generation_jobs', ['retry_count', 'status'])
    op.create_index('idx_generation_jobs_total_cost', 'generation_jobs', ['total_cost_usd'])
    
    # Create content_reservations table
    op.create_table(
        'content_reservations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('intent_hash', sa.String(), nullable=False),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id', ondelete='SET NULL'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('fulfilled_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('length(trim(intent_hash)) > 0', name='chk_intent_hash_not_empty'),
        sa.CheckConstraint('expires_at > created_at', name='chk_reservation_not_expired'),
    )
    op.create_index('idx_reservations_site_id', 'content_reservations', ['site_id'])
    op.create_index('idx_reservations_intent_hash', 'content_reservations', ['site_id', 'intent_hash'])
    op.create_index('idx_reservations_expires_at', 'content_reservations', ['expires_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('content_reservations')
    op.drop_table('generation_jobs')
    op.drop_table('anchor_links')
    op.drop_table('cluster_pages')
    op.drop_table('clusters')
    op.drop_table('cannibalization_checks')
    op.drop_table('system_events')
    op.drop_table('page_silos')
    op.drop_table('silos')
    op.drop_table('keywords')
    op.drop_table('pages')
    op.drop_table('sites')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS content_status')
    op.execute('DROP TYPE IF EXISTS site_type_enum')
    
    # Drop extensions (be careful - only if not used elsewhere)
    # op.execute('DROP EXTENSION IF EXISTS "vector"')
    # op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')

