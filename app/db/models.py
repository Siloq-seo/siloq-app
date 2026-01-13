"""Database models for Siloq governance engine - Schema v1.1 + v1.3.1"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, 
    ForeignKey, JSON, Enum, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import enum
import uuid

from app.core.database import Base


class ContentStatus(str, enum.Enum):
    """Content publication status"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    DECOMMISSIONED = "decommissioned"
    BLOCKED = "blocked"


class SiteType(str, enum.Enum):
    """Site type enumeration"""
    LOCAL_SERVICE = "LOCAL_SERVICE"
    ECOMMERCE = "ECOMMERCE"


class Site(Base):
    """Site/Website entity"""
    __tablename__ = "sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    domain = Column(String, unique=True, nullable=False)
    site_type = Column(
        Enum(SiteType, name="site_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=True
    )
    
    # LOCAL_SERVICE required fields
    geo_coordinates = Column(JSONB, nullable=True)  # {"lat": float, "lng": float}
    service_area = Column(JSONB, nullable=True)  # ["area1", "area2", ...]
    
    # ECOMMERCE required fields
    product_sku_pattern = Column(String, nullable=True)  # e.g., "PROD-{category}-{id}"
    currency_settings = Column(JSONB, nullable=True)  # {"default": "USD", "supported": [...]}
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    pages = relationship("Page", back_populates="site", cascade="all, delete-orphan")
    silos = relationship("Silo", back_populates="site", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="chk_site_name_not_empty"),
        CheckConstraint("length(trim(domain)) > 0", name="chk_site_domain_not_empty"),
    )


class Page(Base):
    """Core content page with normalized path enforcement"""
    __tablename__ = "pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    
    # Path management
    path = Column(Text, nullable=False)
    # Note: normalized_path is a generated column in PostgreSQL
    # SQLAlchemy doesn't directly support GENERATED columns, so we handle it in migrations
    
    # Content
    title = Column(Text, nullable=False)
    body = Column(Text)
    
    # Proposal flag (v1.3.1)
    is_proposal = Column(Boolean, nullable=False, default=False)
    
    # Status
    status = Column(
        Enum(ContentStatus, name="content_status", values_callable=lambda x: [e.value for e in x]),
        default=ContentStatus.DRAFT,
        nullable=False
    )
    
    # Authority preservation
    authority_score = Column(Float, default=0.0)
    source_urls = Column(JSONB, default=lambda: [])
    
    # Governance checks (Week 5 Refactor)
    governance_checks = Column(JSONB, default=lambda: {})
    
    # V2 Dormant Fields - Added for forward compatibility
    # These fields will be used in V2 but are safe to add now (pre-launch)
    v2_governance = Column(
        JSONB,
        default=lambda: {
            "signal_status": "IDLE",  # IDLE, ACTIVE, PAUSED
            "enforcement_log": [],
        },
        nullable=False
    )
    active_widget_id = Column(UUID(as_uuid=True), nullable=True)  # V2: Active widget reference
    widget_config_payload = Column(JSONB, default=lambda: {}, nullable=False)  # V2: Widget configuration
    
    # Page type (V1 Stress Test: Product, Service_Core, Blog, Supporting)
    # Stored in governance_checks for flexibility, can be migrated to column later
    # page_type = Column(String, nullable=True)  # Future: Add as column if needed
    
    # Vector embedding for cannibalization detection
    embedding = Column(Vector(1536))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)
    decommissioned_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    site = relationship("Site", back_populates="pages")
    keyword = relationship("Keyword", back_populates="page", uselist=False, cascade="all, delete-orphan")
    page_silos = relationship("PageSilo", back_populates="page", cascade="all, delete-orphan")
    cannibalization_checks = relationship(
        "CannibalizationCheck",
        foreign_keys="CannibalizationCheck.page_id",
        back_populates="page"
    )
    generation_jobs = relationship("GenerationJob", back_populates="page", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("length(trim(path)) > 0", name="chk_page_path_not_empty"),
        CheckConstraint("length(trim(title)) > 0", name="chk_page_title_not_empty"),
        CheckConstraint("authority_score >= 0.0 AND authority_score <= 1.0", name="chk_authority_score_range"),
        UniqueConstraint("site_id", "normalized_path", name="uniq_page_normalized_path_per_site"),
        Index("idx_pages_site_id", "site_id"),
        Index("idx_pages_normalized_path", "normalized_path"),
        Index("idx_pages_status", "status"),
        Index("idx_pages_is_proposal", "is_proposal"),
    )


class Keyword(Base):
    """Keywords with one-to-one mapping to pages"""
    __tablename__ = "keywords"

    keyword = Column(Text, primary_key=True)
    page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True  # One-to-one mapping: each page can have at most one keyword
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    page = relationship("Page", back_populates="keyword")

    __table_args__ = (
        CheckConstraint("length(trim(keyword)) > 0", name="chk_keyword_not_empty"),
        CheckConstraint("keyword = lower(trim(keyword))", name="chk_keyword_normalized"),
        Index("idx_keywords_page_id", "page_id"),
    )


class Silo(Base):
    """Reverse Silo structure (3-7 silos per site)"""
    __tablename__ = "silos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    position = Column(Integer, nullable=False)  # Order within site (1-7)
    
    # Week 4: Finalization and entity inheritance
    is_finalized = Column(Boolean, nullable=False, default=False)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    entity_type = Column(String, nullable=True)  # e.g., 'topic', 'category', 'service'
    parent_silo_id = Column(UUID(as_uuid=True), ForeignKey("silos.id", ondelete="SET NULL"), nullable=True)
    authority_funnel_score = Column(Float, default=0.0)
    anchor_governance_enabled = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    site = relationship("Site", back_populates="silos")
    page_silos = relationship("PageSilo", back_populates="silo", cascade="all, delete-orphan")
    parent_silo = relationship("Silo", remote_side=[id], backref="child_silos")

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="chk_silo_name_not_empty"),
        CheckConstraint("length(trim(slug)) > 0", name="chk_silo_slug_not_empty"),
        CheckConstraint("position >= 1 AND position <= 7", name="chk_silo_position_range"),
        CheckConstraint("authority_funnel_score >= 0.0 AND authority_funnel_score <= 1.0", name="chk_authority_funnel_score_range"),
        UniqueConstraint("site_id", "position", name="uniq_silo_position_per_site"),
        UniqueConstraint("site_id", "slug", name="uniq_silo_slug_per_site"),
        Index("idx_silos_site_id", "site_id"),
        Index("idx_silos_position", "site_id", "position"),
        Index("idx_silos_is_finalized", "is_finalized"),
        Index("idx_silos_parent_silo_id", "parent_silo_id"),
    )


class PageSilo(Base):
    """Many-to-many relationship between pages and silos"""
    __tablename__ = "page_silos"

    page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pages.id", ondelete="CASCADE"),
        primary_key=True
    )
    silo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("silos.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    # Week 4: Supporting pages
    is_supporting_page = Column(Boolean, nullable=False, default=False)
    supporting_role = Column(String, nullable=True)  # 'pillar', 'cluster', 'topic'
    authority_weight = Column(Float, default=1.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    page = relationship("Page", back_populates="page_silos")
    silo = relationship("Silo", back_populates="page_silos")
    
    __table_args__ = (
        CheckConstraint("authority_weight >= 0.0 AND authority_weight <= 2.0", name="chk_authority_weight_range"),
        Index("idx_page_silos_is_supporting", "is_supporting_page"),
    )


class Organization(Base):
    """Organization: Top-level tenant boundary"""
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="chk_org_name_not_empty"),
        CheckConstraint("length(trim(slug)) > 0", name="chk_org_slug_not_empty"),
        Index("idx_organizations_slug", "slug"),
        Index("idx_organizations_deleted_at", "deleted_at"),
    )


class User(Base):
    """User accounts with authentication and RBAC"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True)  # NULL for OAuth users
    name = Column(String, nullable=True)
    
    # RBAC role
    role = Column(String, nullable=False, default="viewer")
    
    # Security
    generation_enabled = Column(Boolean, nullable=False, default=True)  # Per-user kill switch
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_secret = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="users")

    __table_args__ = (
        CheckConstraint("length(trim(email)) > 0", name="chk_user_email_not_empty"),
        CheckConstraint("role IN ('owner', 'admin', 'editor', 'viewer')", name="chk_user_role_valid"),
        Index("idx_users_email", "email"),
        Index("idx_users_organization_id", "organization_id"),
        Index("idx_users_role", "role"),
    )


class Project(Base):
    """Project: Tenant isolation boundary (maps 1:1 to Site)"""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    
    # Soft delete
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deletion_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="projects")
    site = relationship("Site")
    entitlements = relationship("ProjectEntitlement", back_populates="project", uselist=False, cascade="all, delete-orphan")
    ai_settings = relationship("ProjectAISettings", back_populates="project", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="chk_project_name_not_empty"),
        CheckConstraint("length(trim(slug)) > 0", name="chk_project_slug_not_empty"),
        UniqueConstraint("organization_id", "slug", name="uniq_project_slug_per_org"),
        Index("idx_projects_organization_id", "organization_id"),
        Index("idx_projects_site_id", "site_id"),
        Index("idx_projects_slug", "organization_id", "slug"),
    )


class PlanType(str, enum.Enum):
    """Plan types enumeration"""
    TRIAL = "trial"
    BLUEPRINT = "blueprint"
    OPERATOR = "operator"
    AGENCY = "agency"
    EMPIRE = "empire"


class ProjectEntitlement(Base):
    """Project entitlements and feature access"""
    __tablename__ = "project_entitlements"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    
    # Plan
    plan_key = Column(
        Enum(PlanType, name="plan_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PlanType.TRIAL
    )
    subscription_status = Column(String, default="active")
    subscription_id = Column(String, nullable=True)  # Stripe subscription ID
    stripe_customer_id = Column(String, nullable=True)  # Encrypted in application layer
    
    # Trial
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    trial_started_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Blueprint (one-time unlock)
    blueprint_activation_purchased = Column(Boolean, nullable=False, default=False)
    blueprint_activated_at = Column(DateTime(timezone=True), nullable=True)
    blueprint_target_page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="SET NULL"), nullable=True)
    
    # Usage limits
    max_concurrent_jobs = Column(Integer, default=5)
    max_drafts_per_day = Column(Integer, default=50)
    max_drafts_per_month = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="entitlements")

    __table_args__ = (
        CheckConstraint(
            "subscription_status IN ('active', 'canceled', 'past_due', 'trialing', 'incomplete', 'incomplete_expired')",
            name="chk_subscription_status_valid"
        ),
        Index("idx_project_entitlements_plan_key", "plan_key"),
        Index("idx_project_entitlements_subscription_id", "subscription_id"),
    )


class ProjectAISettings(Base):
    """BYOK (Bring Your Own Key) AI settings with encrypted API keys"""
    __tablename__ = "project_ai_settings"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    
    # BYOK: Encrypted API keys (AES-256-GCM)
    api_key_encrypted = Column(Text, nullable=True)  # Base64-encoded encrypted key
    api_key_iv = Column(Text, nullable=True)  # Base64-encoded IV
    api_key_auth_tag = Column(Text, nullable=True)  # Base64-encoded auth tag
    
    # Provider settings
    ai_provider = Column(String, default="openai")
    ai_model = Column(String, default="gpt-4-turbo-preview")
    
    # Generation controls
    generation_enabled = Column(Boolean, nullable=False, default=True)  # Per-project kill switch
    max_retries = Column(Integer, default=3)
    max_cost_per_job_usd = Column(Float, default=10.0)
    
    # API key validation tracking
    api_key_last_validated_at = Column(DateTime(timezone=True), nullable=True)
    api_key_validation_failures = Column(Integer, default=0)
    api_key_last_failure_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="ai_settings")

    __table_args__ = (
        CheckConstraint("ai_provider IN ('openai', 'anthropic', 'google')", name="chk_ai_provider_valid"),
        CheckConstraint("max_retries > 0", name="chk_max_retries_positive"),
        CheckConstraint("max_cost_per_job_usd >= 0.0", name="chk_max_cost_non_negative"),
    )


class SystemEvent(Base):
    """Enhanced immutable audit logging for all actions (V012)"""
    __tablename__ = "system_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    
    # Actor
    actor_id = Column(UUID(as_uuid=True), nullable=True)  # user or null for system
    actor_type = Column(String, nullable=False)
    actor_ip = Column(String, nullable=True)  # INET in PostgreSQL
    actor_user_agent = Column(Text, nullable=True)
    
    # Event
    event_type = Column(Text, nullable=False)
    severity = Column(String, nullable=False)
    action = Column(Text, nullable=False)
    
    # Target
    target_entity_type = Column(Text, nullable=True)
    target_entity_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Details
    payload = Column(JSONB, nullable=False, default=lambda: {})
    payload_hash = Column(Text, nullable=False)  # SHA-256 hash for integrity
    doctrine_section = Column(Text, nullable=True)
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("length(trim(event_type)) > 0", name="chk_event_type_not_empty"),
        CheckConstraint("actor_type IN ('user', 'system', 'agent')", name="chk_actor_type_valid"),
        CheckConstraint("severity IN ('INFO', 'WARN', 'BLOCK', 'CRITICAL')", name="chk_severity_valid"),
        CheckConstraint("length(trim(action)) > 0", name="chk_action_not_empty"),
        Index("ix_system_events_project_time", "project_id", "created_at"),
        Index("ix_system_events_type", "event_type"),
        Index("ix_system_events_severity", "severity"),
        Index("ix_system_events_actor", "actor_id", "created_at"),
        Index("ix_system_events_target", "target_entity_type", "target_entity_id"),
    )


class AIUsageLog(Base):
    """AI token usage and cost tracking"""
    __tablename__ = "ai_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    generation_job_id = Column(UUID(as_uuid=True), ForeignKey("generation_jobs.id", ondelete="SET NULL"), nullable=True)
    
    # Usage metrics
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    
    # Request metadata
    prompt_length = Column(Integer, nullable=True)
    response_length = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0", name="chk_tokens_non_negative"),
        CheckConstraint("cost_usd >= 0.0", name="chk_cost_non_negative"),
        Index("idx_ai_usage_project_time", "project_id", "created_at"),
        Index("idx_ai_usage_job_id", "generation_job_id"),
    )


class MonthlyUsageSummary(Base):
    """Aggregated monthly usage per project"""
    __tablename__ = "monthly_usage_summary"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    
    # Aggregated metrics
    total_drafts_generated = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    total_jobs = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("month >= 1 AND month <= 12", name="chk_month_range"),
        UniqueConstraint("project_id", "year", "month", name="uniq_monthly_usage_per_project"),
        Index("idx_monthly_usage_project", "project_id", "year", "month"),
    )


class CannibalizationCheck(Base):
    """Cannibalization detection records"""
    __tablename__ = "cannibalization_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    compared_with_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    threshold_exceeded = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    page = relationship("Page", foreign_keys=[page_id], back_populates="cannibalization_checks")
    compared_with = relationship("Page", foreign_keys=[compared_with_id])

    __table_args__ = (
        CheckConstraint("similarity_score >= 0.0 AND similarity_score <= 1.0", name="chk_similarity_score_range"),
        CheckConstraint("page_id != compared_with_id", name="chk_no_self_comparison"),
        Index("idx_cannibalization_page_id", "page_id"),
        Index("idx_cannibalization_compared_with", "compared_with_id"),
        Index("idx_cannibalization_created_at", "created_at"),
    )


class Cluster(Base):
    """Content clusters for grouping related pages"""
    __tablename__ = "clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    cluster_pages = relationship("ClusterPage", back_populates="cluster", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="chk_cluster_name_not_empty"),
        UniqueConstraint("site_id", "name", name="uniq_cluster_name_per_site"),
        Index("idx_clusters_site_id", "site_id"),
    )


class ClusterPage(Base):
    """Many-to-many relationship between clusters and pages"""
    __tablename__ = "cluster_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False, default="member")  # 'member', 'anchor', 'hub'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    cluster = relationship("Cluster", back_populates="cluster_pages")
    page = relationship("Page")

    __table_args__ = (
        CheckConstraint("role IN ('member', 'anchor', 'hub')", name="chk_cluster_page_role_valid"),
        UniqueConstraint("cluster_id", "page_id", name="uniq_cluster_page"),
        Index("idx_cluster_pages_cluster_id", "cluster_id"),
        Index("idx_cluster_pages_page_id", "page_id"),
    )


class AnchorLink(Base):
    """Governed anchor links with authority tracking"""
    __tablename__ = "anchor_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    to_page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    anchor_text = Column(String, nullable=False)
    silo_id = Column(UUID(as_uuid=True), ForeignKey("silos.id", ondelete="SET NULL"), nullable=True)
    is_internal = Column(Boolean, nullable=False, default=True)
    authority_passed = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    from_page = relationship("Page", foreign_keys=[from_page_id])
    to_page = relationship("Page", foreign_keys=[to_page_id])
    silo = relationship("Silo")

    __table_args__ = (
        CheckConstraint("length(trim(anchor_text)) > 0", name="chk_anchor_text_not_empty"),
        CheckConstraint("from_page_id != to_page_id", name="chk_no_self_link"),
        CheckConstraint("authority_passed >= 0.0 AND authority_passed <= 1.0", name="chk_authority_passed_range"),
        UniqueConstraint("from_page_id", "to_page_id", "anchor_text", name="uniq_anchor_link"),
        Index("idx_anchor_links_from_page", "from_page_id"),
        Index("idx_anchor_links_to_page", "to_page_id"),
        Index("idx_anchor_links_silo_id", "silo_id"),
    )


class GenerationJob(Base):
    """AI content generation job tracking with state machine"""
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String, unique=True, nullable=False)  # BullMQ job ID
    
    # Job status (Week 2: Extended with state machine states, Week 5: Added ai_max_retry_exceeded)
    status = Column(
        String(50), 
        default="draft"
    )  # draft, preflight_approved, prompt_locked, processing, postcheck_passed, postcheck_failed, completed, failed, ai_max_retry_exceeded
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)  # Error code from ErrorCodeDictionary
    
    # Week 5: Retry and cost tracking
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    total_cost_usd = Column(Float, default=0.0, nullable=False)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    structured_output_metadata = Column(JSONB, default=lambda: {})  # Entities, FAQs, links metadata
    
    # State transition tracking
    state_transition_history = Column(JSONB, default=lambda: [])  # Store transition history
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    preflight_approved_at = Column(DateTime(timezone=True), nullable=True)
    prompt_locked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    page = relationship("Page", back_populates="generation_jobs")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'preflight_approved', 'prompt_locked', 'processing', 'postcheck_passed', 'postcheck_failed', 'completed', 'failed', 'ai_max_retry_exceeded')", 
            name="chk_job_status_valid"
        ),
        CheckConstraint("length(trim(job_id)) > 0", name="chk_job_id_not_empty"),
        CheckConstraint("retry_count >= 0", name="chk_retry_count_non_negative"),
        CheckConstraint("max_retries > 0", name="chk_max_retries_positive"),
        CheckConstraint("total_cost_usd >= 0.0", name="chk_total_cost_non_negative"),
        Index("idx_generation_jobs_page_id", "page_id"),
        Index("idx_generation_jobs_status", "status"),
        Index("idx_generation_jobs_job_id", "job_id"),
        Index("idx_generation_jobs_retry_count", "retry_count", "status"),
        Index("idx_generation_jobs_total_cost", "total_cost_usd"),
    )


class ContentReservation(Base):
    """Content slot reservations for planning collision prevention"""
    __tablename__ = "content_reservations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    intent_hash = Column(String, nullable=False)  # MD5 hash of intent (title + location)
    location = Column(String, nullable=True)  # Geographic location
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    site = relationship("Site")
    page = relationship("Page")

    __table_args__ = (
        CheckConstraint("length(trim(intent_hash)) > 0", name="chk_intent_hash_not_empty"),
        CheckConstraint("expires_at > created_at", name="chk_reservation_not_expired"),
        Index("idx_reservations_site_id", "site_id"),
        Index("idx_reservations_intent_hash", "site_id", "intent_hash"),
        Index("idx_reservations_expires_at", "expires_at"),
    )
