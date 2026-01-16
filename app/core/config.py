"""Application configuration"""
from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str
    database_url_sync: str

    @field_validator('database_url')
    @classmethod
    def ensure_async_driver(cls, v: str) -> str:
        """
        Ensure DATABASE_URL uses asyncpg driver for async SQLAlchemy.

        Digital Ocean and other platforms may inject postgresql:// URLs,
        but we need postgresql+asyncpg:// for async operations.
        """
        if v.startswith('postgresql://') and '+asyncpg' not in v:
            return v.replace('postgresql://', 'postgresql+asyncpg://', 1)
        return v

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
    
    # CORS Configuration
    cors_origins: str = "*"  # Comma-separated list of allowed origins, or "*" for all
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "*"  # Comma-separated list or "*" for all
    cors_allow_headers: str = "*"  # Comma-separated list or "*" for all
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60  # Requests per minute per site/account
    rate_limit_per_hour: int = 1000  # Requests per hour per site/account
    rate_limit_per_day: int = 10000  # Requests per day per site/account
    
    # Production Guardrails
    global_generation_enabled: bool = True  # Global kill switch for content generation
    max_jobs_per_hour: int = 100  # Maximum generation jobs per hour globally
    max_jobs_per_day: int = 1000  # Maximum generation jobs per day globally

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
    
    # 2025 SEO Alignment Settings
    # Experience Verification
    min_experience_indicators: int = 2
    max_generic_indicators: int = 3
    
    # GEO Formatting
    direct_answer_max_chars: int = 200
    min_bullet_points: int = 3
    min_headings: int = 2
    
    # Core Web Vitals Thresholds
    cls_threshold: float = 0.1  # Cumulative Layout Shift
    lcp_threshold: float = 2.5  # Largest Contentful Paint (seconds)
    fid_threshold: float = 100.0  # First Input Delay (milliseconds, legacy)
    
    # 2026 Performance Enhancements
    inp_threshold: float = 200.0  # Interaction to Next Paint (milliseconds)
    performance_budget_mb: float = 2.0  # Performance budget in MB (payload size limit)
    
    # Correction Sprint: Tone Governance (Section 6.1)
    # Supported brand voice tones - replaces free-text input
    SUPPORTED_TONES: dict = {
        "AUTHORITY": "Professional, data-driven, clinical. Use authoritative, technical language. Demonstrate deep expertise and knowledge. Use industry terminology appropriately. Provide detailed explanations and technical specifications. Maintain professional, credible tone throughout.",
        "NEIGHBOR": "Friendly, local, accessible, first-person. Use warm, friendly 'You/We' language. Write as if speaking to a neighbor or friend. Include local references and relatable examples. Use conversational tone, avoid overly formal language. Show empathy and understanding of customer needs.",
        "HYPE": "High-energy, sales-focused, urgent. Use energetic, sales-focused language. Create excitement and urgency. Highlight benefits and outcomes. Use action-oriented, compelling language. Focus on transformation and results.",
    }

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

