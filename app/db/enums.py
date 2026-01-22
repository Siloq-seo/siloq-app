"""Database model enumerations"""
import enum


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


class PlanType(str, enum.Enum):
    """Plan types enumeration"""
    TRIAL = "trial"
    BLUEPRINT = "blueprint"
    OPERATOR = "operator"
    AGENCY = "agency"
    EMPIRE = "empire"
