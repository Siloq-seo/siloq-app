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


class Site(Base):
    """Site/Website entity"""
    __tablename__ = "sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    domain = Column(String, unique=True, nullable=False)
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


class SystemEvent(Base):
    """Comprehensive audit logging for all schema changes (v1.3.1)"""
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    payload = Column(JSONB, default=lambda: {})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("length(trim(event_type)) > 0", name="chk_event_type_not_empty"),
        CheckConstraint("length(trim(entity_type)) > 0", name="chk_entity_type_not_empty"),
        Index("idx_system_events_entity", "entity_type", "entity_id"),
        Index("idx_system_events_created_at", "created_at"),
        Index("idx_system_events_type", "event_type"),
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
