"""Application configuration"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str
    database_url_sync: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # pgvector
    vector_dimension: int = 1536

    # Governance Settings
    min_reverse_silos: int = 3
    max_reverse_silos: int = 7
    cannibalization_threshold: float = 0.85

    # Week 5: AI Draft Engine Settings
    ai_max_retries: int = 3
    ai_max_cost_per_job_usd: float = 10.0  # Maximum cost per job in USD
    min_faq_count: int = 3
    min_entity_count: int = 3

    # Week 6: Lifecycle Gates Settings
    min_title_length: int = 10
    min_body_length: int = 500
    min_slug_length: int = 3
    authority_threshold_for_sources: float = 0.5  # Require sources if authority > this

    # Silo Decay Settings
    silo_decay_threshold_days: int = 90  # Days before stale proposals/orphaned pages are decommissioned

    # Content Structure Settings
    max_title_length: int = 200
    max_slug_length: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

