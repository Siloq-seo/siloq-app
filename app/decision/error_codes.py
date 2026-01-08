"""Error Code Dictionary v1.4 - Standardized error responses with doctrine references."""
from dataclasses import dataclass
from typing import ClassVar, Dict, List, Optional

from enum import Enum


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    
    ERROR = "error"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ErrorCode:
    """
    Standardized error code with doctrine reference and remediation.
    
    Attributes:
        code: Unique error code identifier (e.g., PREFLIGHT_001)
        message: Human-readable error message
        doctrine_reference: Reference to violated policy/rule
        remediation_steps: List of steps to resolve the error
        severity: Error severity level
    """
    
    code: str
    message: str
    doctrine_reference: str
    remediation_steps: List[str]
    severity: str = ErrorSeverity.ERROR.value
    
    def to_dict(self) -> Dict[str, str]:
        """Convert error code to dictionary for API responses."""
        return {
            "code": self.code,
            "message": self.message,
            "doctrine_reference": self.doctrine_reference,
            "remediation_steps": self.remediation_steps,
            "severity": self.severity,
        }


class ErrorCodeDictionary:
    """
    Error Code Dictionary v1.4 - Comprehensive error catalog.
    
    Provides standardized error codes with doctrine references and
    remediation steps for all validation and state machine errors.
    """
    
    # Preflight Validation Errors (PREFLIGHT_*)
    PREFLIGHT_001: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_001",
        message="Page path already exists in site",
        doctrine_reference="DOCTRINE-STRUCTURE-001: Unique normalized paths",
        remediation_steps=[
            "Check if page with same normalized path exists",
            "Use different path or update existing page",
            "Verify site_id is correct",
        ],
    )
    
    PREFLIGHT_002: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_002",
        message="Site does not have valid silo structure (3-7 silos required)",
        doctrine_reference="DOCTRINE-STRUCTURE-002: Reverse Silos (3-7 per site)",
        remediation_steps=[
            "Ensure site has between 3 and 7 silos",
            "Add or remove silos to meet requirement",
            "Verify silo positions are sequential (1-7)",
        ],
    )
    
    PREFLIGHT_003: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_003",
        message="Silo not found or does not belong to site",
        doctrine_reference="DOCTRINE-STRUCTURE-003: Silo ownership",
        remediation_steps=[
            "Verify silo_id exists",
            "Ensure silo belongs to the specified site",
            "Check silo is not decommissioned",
        ],
    )
    
    PREFLIGHT_004: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_004",
        message="Page title is too short (minimum 10 characters)",
        doctrine_reference="DOCTRINE-CONTENT-001: Title structure",
        remediation_steps=[
            "Ensure title is at least 10 characters",
            "Remove leading/trailing whitespace",
            "Verify title is not empty",
        ],
    )
    
    PREFLIGHT_005: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_005",
        message="Page path format is invalid",
        doctrine_reference="DOCTRINE-STRUCTURE-004: Path format validation",
        remediation_steps=[
            "Path must start with '/'",
            "No consecutive slashes allowed",
            "Path cannot end with '/' (except root)",
        ],
    )
    
    PREFLIGHT_006: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_006",
        message="Keyword already mapped to another page",
        doctrine_reference="DOCTRINE-CANONICAL-001: One-to-one keyword mapping",
        remediation_steps=[
            "Check if keyword already exists",
            "Use different keyword or update existing mapping",
            "Verify canonical uniqueness constraint",
        ],
    )
    
    PREFLIGHT_007: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_007",
        message="Page would cannibalize existing published content",
        doctrine_reference="DOCTRINE-CANNIBALIZATION-001: Semantic similarity threshold",
        remediation_steps=[
            "Review similar content identified",
            "Modify content to reduce similarity",
            "Consider updating existing content instead",
            "Check similarity score against threshold (0.85)",
        ],
    )
    
    NEAR_DUPLICATE_INTENT: ClassVar[ErrorCode] = ErrorCode(
        code="NEAR_DUPLICATE_INTENT",
        message="Content has near-duplicate intent (similarity >= 0.85)",
        doctrine_reference="DOCTRINE-CANNIBALIZATION-002: Near-duplicate intent detection",
        remediation_steps=[
            "Review similar content with high similarity score",
            "Modify content to differentiate intent",
            "Check if geo-exception applies (different locations)",
            "Consider updating existing content instead",
            "Verify similarity score is below 0.85 threshold",
        ],
    )
    _register_error(NEAR_DUPLICATE_INTENT)
    
    PREFLIGHT_008: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_008",
        message="Page is a proposal and has exceeded decay threshold (90 days)",
        doctrine_reference="DOCTRINE-DECAY-001: SILO_DECAY trigger",
        remediation_steps=[
            "Convert proposal to active page",
            "Update proposal content",
            "Remove is_proposal flag if content is ready",
        ],
        severity=ErrorSeverity.WARNING.value,
    )
    
    PREFLIGHT_009: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_009",
        message="Site not found",
        doctrine_reference="DOCTRINE-STRUCTURE-005: Site existence",
        remediation_steps=[
            "Verify site_id is correct",
            "Check site exists and is not decommissioned",
            "Create site if it doesn't exist",
        ],
    )
    
    PREFLIGHT_010: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_010",
        message="Page body is required for generation",
        doctrine_reference="DOCTRINE-CONTENT-002: Content completeness",
        remediation_steps=[
            "Provide page body content",
            "Ensure body is not empty",
            "Verify content structure is valid",
        ],
    )
    
    PREFLIGHT_011: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_011",
        message="LOCAL_SERVICE site requires geo_coordinates and service_area",
        doctrine_reference="DOCTRINE-SCOPE-001: Site type validation",
        remediation_steps=[
            "Set site_type to LOCAL_SERVICE or ECOMMERCE",
            "For LOCAL_SERVICE: Provide geo_coordinates (lat/lng) and service_area array",
            "For ECOMMERCE: Provide product_sku_pattern and currency_settings",
        ],
    )
    
    PREFLIGHT_012: ClassVar[ErrorCode] = ErrorCode(
        code="PREFLIGHT_012",
        message="ECOMMERCE site requires product_sku_pattern and currency_settings",
        doctrine_reference="DOCTRINE-SCOPE-001: Site type validation",
        remediation_steps=[
            "Set site_type to LOCAL_SERVICE or ECOMMERCE",
            "For LOCAL_SERVICE: Provide geo_coordinates (lat/lng) and service_area array",
            "For ECOMMERCE: Provide product_sku_pattern and currency_settings",
        ],
    )
    
    # State Machine Errors (STATE_*)
    STATE_001: ClassVar[ErrorCode] = ErrorCode(
        code="STATE_001",
        message="Invalid state transition attempted",
        doctrine_reference="DOCTRINE-STATE-001: State transition rules",
        remediation_steps=[
            "Review valid state transitions",
            "Ensure previous state allows this transition",
            "Check state transition history",
        ],
    )
    
    STATE_002: ClassVar[ErrorCode] = ErrorCode(
        code="STATE_002",
        message="Cannot proceed without PREFLIGHT_APPROVED state",
        doctrine_reference="DOCTRINE-STATE-002: Preflight requirement",
        remediation_steps=[
            "Run preflight validation first",
            "Resolve all preflight errors",
            "Ensure state is PREFLIGHT_APPROVED before proceeding",
        ],
    )
    
    STATE_003: ClassVar[ErrorCode] = ErrorCode(
        code="STATE_003",
        message="State transition skipped (invalid sequence)",
        doctrine_reference="DOCTRINE-STATE-003: Sequential state enforcement",
        remediation_steps=[
            "Follow required state sequence",
            "Do not skip intermediate states",
            "Review state machine documentation",
        ],
    )
    
    STATE_004: ClassVar[ErrorCode] = ErrorCode(
        code="STATE_004",
        message="Job state is locked and cannot be modified",
        doctrine_reference="DOCTRINE-STATE-004: State locking",
        remediation_steps=[
            "Check current job state",
            "Wait for current operation to complete",
            "Review job status before attempting changes",
        ],
    )
    
    # Post-Check Errors (POSTCHECK_*)
    POSTCHECK_001: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_001",
        message="Generated content failed cannibalization check",
        doctrine_reference="DOCTRINE-CANNIBALIZATION-002: Post-generation similarity",
        remediation_steps=[
            "Review generated content",
            "Modify content to reduce similarity",
            "Check embedding similarity scores",
        ],
    )
    
    POSTCHECK_002: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_002",
        message="Generated content length is invalid (500-50,000 chars required)",
        doctrine_reference="DOCTRINE-CONTENT-003: Content length constraints",
        remediation_steps=[
            "Ensure content is between 500 and 50,000 characters",
            "Expand or reduce content as needed",
            "Verify content completeness",
        ],
    )
    
    POSTCHECK_003: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_003",
        message="Generated content lacks sufficient sentence structure (minimum 5 sentences)",
        doctrine_reference="DOCTRINE-CONTENT-004: Sentence structure",
        remediation_steps=[
            "Ensure content has at least 5 complete sentences",
            "Review sentence quality and structure",
            "Add more content if needed",
        ],
    )
    
    POSTCHECK_004: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_004",
        message="Generated content does not preserve intent (keyword presence check failed)",
        doctrine_reference="DOCTRINE-INTENT-001: Intent preservation",
        remediation_steps=[
            "Ensure title keywords appear in content",
            "Review keyword-to-content ratio (minimum 0.3)",
            "Improve content relevance to title",
        ],
    )
    
    POSTCHECK_005: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_005",
        message="High authority content requires source URLs",
        doctrine_reference="DOCTRINE-AUTHORITY-001: Authority preservation",
        remediation_steps=[
            "Add source URLs for high-authority content (score > 0.7)",
            "Provide credible source references",
            "Update authority score if sources unavailable",
        ],
    )
    
    POSTCHECK_006: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_006",
        message="Content completeness check failed (missing required fields)",
        doctrine_reference="DOCTRINE-CONTENT-005: Content completeness",
        remediation_steps=[
            "Ensure title, slug, and body are present",
            "Verify all required fields are populated",
            "Check content structure is complete",
        ],
    )
    
    # System Errors (SYSTEM_*)
    SYSTEM_001: ClassVar[ErrorCode] = ErrorCode(
        code="SYSTEM_001",
        message="Database connection failed",
        doctrine_reference="DOCTRINE-SYSTEM-001: Database availability",
        remediation_steps=[
            "Check database connection",
            "Verify database is running",
            "Review connection configuration",
        ],
        severity=ErrorSeverity.CRITICAL.value,
    )
    
    SYSTEM_002: ClassVar[ErrorCode] = ErrorCode(
        code="SYSTEM_002",
        message="Embedding generation failed",
        doctrine_reference="DOCTRINE-SYSTEM-002: Embedding service",
        remediation_steps=[
            "Check embedding service availability",
            "Verify API keys are configured",
            "Retry embedding generation",
        ],
    )
    
    # Week 5: AI Draft Engine Errors (AI_*)
    AI_MAX_RETRY_EXCEEDED: ClassVar[ErrorCode] = ErrorCode(
        code="AI_MAX_RETRY_EXCEEDED",
        message="Maximum retry attempts exceeded for AI generation",
        doctrine_reference="DOCTRINE-AI-001: Retry limit enforcement",
        remediation_steps=[
            "Review generation job error history",
            "Check if prompt needs adjustment",
            "Verify content requirements are achievable",
            "Consider manual content creation if retries consistently fail",
        ],
        severity=ErrorSeverity.CRITICAL.value,
    )
    
    AI_COST_LIMIT_EXCEEDED: ClassVar[ErrorCode] = ErrorCode(
        code="AI_COST_LIMIT_EXCEEDED",
        message="AI generation cost exceeded maximum allowed per job",
        doctrine_reference="DOCTRINE-AI-002: Cost limit enforcement",
        remediation_steps=[
            "Review job cost breakdown",
            "Optimize prompt to reduce token usage",
            "Consider using cheaper model if appropriate",
            "Adjust max_cost_per_job_usd setting if needed",
        ],
        severity=ErrorSeverity.ERROR.value,
    )
    
    # Week 5: Postcheck Enhancement Errors (POSTCHECK_*)
    POSTCHECK_007: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_007",
        message="Insufficient entity coverage (minimum 3 entities required)",
        doctrine_reference="DOCTRINE-CONTENT-006: Entity coverage requirement",
        remediation_steps=[
            "Ensure content mentions at least 3 distinct entities",
            "Review generated content for entity mentions",
            "Regenerate with explicit entity requirements",
        ],
    )
    
    POSTCHECK_008: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_008",
        message="Insufficient FAQ coverage (minimum 3 FAQs required)",
        doctrine_reference="DOCTRINE-CONTENT-007: FAQ schema enforcement",
        remediation_steps=[
            "Ensure content includes at least 3 FAQs",
            "Each FAQ must have both question and answer",
            "Regenerate with explicit FAQ requirements",
        ],
    )
    
    POSTCHECK_009: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_009",
        message="Hallucinated or invalid links detected",
        doctrine_reference="DOCTRINE-CONTENT-008: Link validation rules",
        remediation_steps=[
            "Remove or replace invalid links",
            "Verify all URLs are real and accessible",
            "Ensure links are not hallucinated by AI",
            "Regenerate content with link validation requirements",
        ],
    )
    
    POSTCHECK_010: ClassVar[ErrorCode] = ErrorCode(
        code="POSTCHECK_010",
        message="FAQ schema validation failed (missing question or answer)",
        doctrine_reference="DOCTRINE-CONTENT-007: FAQ schema enforcement",
        remediation_steps=[
            "Ensure all FAQs have both 'question' and 'answer' fields",
            "Validate FAQ structure matches required schema",
            "Regenerate content with proper FAQ format",
        ],
    )
    
    # Week 6: Lifecycle Gates Errors (LIFECYCLE_*)
    LIFECYCLE_001: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_001",
        message="Cannot publish: Governance checks gate failed",
        doctrine_reference="DOCTRINE-PUBLISH-001: Governance checks requirement",
        remediation_steps=[
            "Ensure all governance checks have passed (pre_generation, during_generation, post_generation)",
            "Review governance_checks in page metadata",
            "Re-run validation if needed",
        ],
    )
    
    LIFECYCLE_002: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_002",
        message="Cannot publish: Schema sync validation failed",
        doctrine_reference="DOCTRINE-PUBLISH-002: Schema-content synchronization",
        remediation_steps=[
            "Regenerate JSON-LD schema to match current content",
            "Verify schema headline matches page title",
            "Verify schema URL matches page path",
            "Check schema dates match page timestamps",
        ],
    )
    
    LIFECYCLE_003: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_003",
        message="Cannot publish: Embedding gate failed",
        doctrine_reference="DOCTRINE-PUBLISH-003: Embedding requirement",
        remediation_steps=[
            "Generate vector embedding for the page",
            "Ensure embedding exists before publishing",
            "Verify embedding dimension is correct (1536)",
        ],
    )
    
    LIFECYCLE_004: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_004",
        message="Cannot publish: Authority gate failed",
        doctrine_reference="DOCTRINE-PUBLISH-004: Authority validation",
        remediation_steps=[
            "Add source URLs for high-authority content (score > 0.5)",
            "Provide credible source references",
            "Update authority score if sources unavailable",
        ],
    )
    
    LIFECYCLE_005: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_005",
        message="Cannot publish: Content structure gate failed",
        doctrine_reference="DOCTRINE-PUBLISH-005: Content structure validation",
        remediation_steps=[
            "Ensure title is at least 10 characters",
            "Ensure body is at least 500 characters",
            "Verify path starts with '/'",
        ],
    )
    
    LIFECYCLE_006: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_006",
        message="Cannot publish: Status gate failed",
        doctrine_reference="DOCTRINE-PUBLISH-006: Status validation",
        remediation_steps=[
            "Content status must be APPROVED or DRAFT to publish",
            "BLOCKED content cannot be published",
            "DECOMMISSIONED content cannot be published",
        ],
    )
    
    LIFECYCLE_007: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_007",
        message="Invalid redirect URL for decommission",
        doctrine_reference="DOCTRINE-DECOMMISSION-001: Redirect validation",
        remediation_steps=[
            "Ensure redirect URL is valid (internal path or external URL)",
            "If internal, verify target page exists and is published",
            "Check redirect URL format",
        ],
    )
    
    # 2025 SEO Alignment: New Lifecycle Gates
    LIFECYCLE_008: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_008",
        message="Cannot publish: Experience verification gate failed",
        doctrine_reference="DOCTRINE-2025-EXPERIENCE-001: First-hand experience requirement",
        remediation_steps=[
            "Add specific data points, statistics, or metrics to content",
            "Include case studies or real-world examples",
            "Add first-hand anecdotes or personal experiences",
            "Replace generic statements with concrete evidence",
            "Ensure content demonstrates real-world experience (minimum 2 experience indicators)",
        ],
    )
    
    LIFECYCLE_009: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_009",
        message="Cannot publish: GEO formatting gate failed",
        doctrine_reference="DOCTRINE-2025-GEO-001: AI citation-ready formatting",
        remediation_steps=[
            "Add direct answer at the top of content (first 200 characters)",
            "Include bullet points for key information (minimum 3 bullets)",
            "Add clear section headings (minimum 2 headings)",
            "Include FAQ section with at least 2 question-answer pairs",
            "Use structured formatting (lists, tables) for easy AI citation",
        ],
    )
    
    LIFECYCLE_010: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_010",
        message="Cannot publish: Core Web Vitals gate failed",
        doctrine_reference="DOCTRINE-2025-MOBILE-001: Mobile-first rendering validation",
        remediation_steps=[
            "Add width and height attributes to images to prevent CLS",
            "Add loading='lazy' to images for better performance",
            "Optimize images and reduce resource count to improve LCP",
            "Reduce JavaScript execution time to improve FID",
            "Ensure mobile viewport is properly configured",
        ],
    )
    
    LIFECYCLE_011: ClassVar[ErrorCode] = ErrorCode(
        code="LIFECYCLE_011",
        message="Link density exceeds maximum allowed ratios",
        doctrine_reference="DOCTRINE-LINK-001: Link density enforcement (Section 8.2)",
        remediation_steps=[
            "Reduce external links to maximum 1 per 400 words",
            "Reduce internal links to maximum 3 per 400 words",
            "Review content and remove excessive links",
            "Ensure link density ratios are within acceptable limits",
        ],
    )
    
    # Entitlement Errors (Section 8)
    ENTITLEMENT_REQUIRED: ClassVar[ErrorCode] = ErrorCode(
        code="ENTITLEMENT_REQUIRED",
        message="This feature requires a paid plan",
        doctrine_reference="Section 8: Entitlement & Plan Enforcement",
        remediation_steps=[
            "Upgrade to a paid plan to access this feature",
            "Review plan tiers: trial, blueprint, operator, agency, empire",
            "Contact support for assistance with plan selection",
        ],
        severity=ErrorSeverity.ERROR.value,
    )
    
    PLAN_LIMIT_EXCEEDED: ClassVar[ErrorCode] = ErrorCode(
        code="PLAN_LIMIT_EXCEEDED",
        message="Your plan limit has been reached",
        doctrine_reference="Section 8: Plan Limits Enforcement",
        remediation_steps=[
            "Upgrade to a higher tier plan",
            "Wait for next billing cycle to reset limits",
            "Contact support to discuss custom limits",
        ],
        severity=ErrorSeverity.ERROR.value,
    )
    
    PROJECT_LIMIT_REACHED: ClassVar[ErrorCode] = ErrorCode(
        code="PROJECT_LIMIT_REACHED",
        message="Maximum number of projects for your plan",
        doctrine_reference="Section 8: Project Limits",
        remediation_steps=[
            "Upgrade to a plan with more projects allowed",
            "Remove unused projects to free up slots",
            "Contact support for custom enterprise plans",
        ],
        severity=ErrorSeverity.ERROR.value,
    )
    
    BLUEPRINT_ALREADY_USED: ClassVar[ErrorCode] = ErrorCode(
        code="BLUEPRINT_ALREADY_USED",
        message="Blueprint activation allows one target page only",
        doctrine_reference="Section 8: Blueprint Activation",
        remediation_steps=[
            "Blueprint activation can only be used once per project",
            "Upgrade to Operator plan for unlimited silos",
            "Contact support if you need to reset blueprint activation",
        ],
        severity=ErrorSeverity.ERROR.value,
    )
    
    # Security Errors (Section 7)
    CROSS_PROJECT_ACCESS_DENIED: ClassVar[ErrorCode] = ErrorCode(
        code="CROSS_PROJECT_ACCESS_DENIED",
        message="Access denied: Cross-project access violation",
        doctrine_reference="Section 7: Tenant Isolation",
        remediation_steps=[
            "Ensure project belongs to your organization",
            "Verify project_id in request is correct",
            "Contact support if you believe this is an error",
        ],
        severity=ErrorSeverity.CRITICAL.value,
    )
    
    PROMPT_SCOPE_VIOLATION: ClassVar[ErrorCode] = ErrorCode(
        code="PROMPT_SCOPE_VIOLATION",
        message="Prompt contains forbidden cross-project data",
        doctrine_reference="Section 7: Prompt Isolation",
        remediation_steps=[
            "Remove forbidden data from prompt",
            "Ensure prompt only contains project-scoped data",
            "Review prompt isolation guidelines",
        ],
        severity=ErrorSeverity.CRITICAL.value,
    )
    
    AI_GENERATION_GLOBALLY_DISABLED: ClassVar[ErrorCode] = ErrorCode(
        code="AI_GENERATION_GLOBALLY_DISABLED",
        message="AI generation is globally disabled",
        doctrine_reference="Section 7: Kill Switch",
        remediation_steps=[
            "AI generation has been disabled system-wide",
            "Contact support for more information",
            "Check system status page for updates",
        ],
        severity=ErrorSeverity.CRITICAL.value,
    )
    
    AI_GENERATION_DISABLED_FOR_PROJECT: ClassVar[ErrorCode] = ErrorCode(
        code="AI_GENERATION_DISABLED_FOR_PROJECT",
        message="AI generation is disabled for this project",
        doctrine_reference="Section 7: Per-Project Kill Switch",
        remediation_steps=[
            "AI generation has been disabled for this project",
            "Contact support to re-enable generation",
            "Check project AI settings",
        ],
        severity=ErrorSeverity.WARNING.value,
    )
    
    AI_GENERATION_DISABLED_FOR_USER: ClassVar[ErrorCode] = ErrorCode(
        code="AI_GENERATION_DISABLED_FOR_USER",
        message="AI generation is disabled for your account",
        doctrine_reference="Section 7: Per-User Kill Switch",
        remediation_steps=[
            "AI generation has been disabled for your account",
            "Contact your organization administrator",
            "Check account settings or contact support",
        ],
        severity=ErrorSeverity.WARNING.value,
    )
    
    # Error code registry for efficient lookup
    _ERROR_REGISTRY: ClassVar[Dict[str, ErrorCode]] = {}
    
    @classmethod
    def _build_registry(cls) -> Dict[str, ErrorCode]:
        """Build error code registry from class attributes."""
        if not cls._ERROR_REGISTRY:
            for attr_name in dir(cls):
                if not attr_name.startswith("_"):
                    attr = getattr(cls, attr_name)
                    if isinstance(attr, ErrorCode):
                        cls._ERROR_REGISTRY[attr.code] = attr
        return cls._ERROR_REGISTRY
    
    @classmethod
    def get_error(cls, code: str) -> Optional[ErrorCode]:
        """
        Get error code by code string.
        
        Args:
            code: Error code identifier (e.g., "PREFLIGHT_001")
            
        Returns:
            ErrorCode if found, None otherwise
        """
        registry = cls._build_registry()
        return registry.get(code)
    
    @classmethod
    def get_all_errors(cls) -> List[ErrorCode]:
        """
        Get all error codes in the dictionary.
        
        Returns:
            List of all ErrorCode instances
        """
        registry = cls._build_registry()
        return list(registry.values())
    
    @classmethod
    def get_errors_by_category(cls, category: str) -> List[ErrorCode]:
        """
        Get errors by category prefix.
        
        Args:
            category: Category prefix (e.g., 'PREFLIGHT', 'STATE')
            
        Returns:
            List of ErrorCode instances matching the category
        """
        prefix = category.upper()
        return [
            error
            for error in cls.get_all_errors()
            if error.code.startswith(prefix)
        ]
