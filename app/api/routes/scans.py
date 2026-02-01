"""Website scanning API routes with Scoring Algorithm v1.1"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional, Dict, Any
from uuid import UUID
from urllib.parse import urlparse
from datetime import datetime

from app.core.database import get_db
from app.db.models import Scan, Site
from app.schemas.scans import (
    ScanRequest,
    ScanResponse,
    ScanSummary,
    ScanReportResponse,
    ScanReportSummary,
    KeywordCannibalizationItem,
)
from app.services.scanning import WebsiteScanner


router = APIRouter(prefix="/scans", tags=["scans"])


# =============================================================================
# SCORING ALGORITHM v1.1 - IMPLEMENTATION IN scans.py
# =============================================================================
# Philosophy: Cannibalization is Siloq's core value prop. Sites with keyword
# cannibalization issues MUST NOT receive A-grades. The scoring system
# prioritizes cannibalization detection above all else.
#
# Key Principle: We show the truth. Clean sites get good scores. Sites with
# real problems get scores that reflect the severity.
#
# Calculation Order (CRITICAL - DO NOT REORDER):
# Step 1: Start with 100 points
# Step 2: Count and classify cannibalization conflicts (weighted by severity)
# Step 3: Apply ALL deductions first (technical, content, CWV, structural)
# Step 4: Apply same-intent multiplier (1.3x) for issues on conflicting pages
# Step 5: Apply bonus points (max +15)
# Step 6: Apply cannibalization cap (can only LOWER score, never raise it)
# Step 7: Apply page count adjustment to cap
# Step 8: Floor at 0, ceiling at 100
# Step 9: Assign grade based on final score
#
# Why this order matters:
# - Deductions FIRST prevents backwards results where a site with 5 conflicts
#   and few other issues scores higher than a site with 3 conflicts and many issues
# - The cap is a CEILING, not a floor - it sets maximum possible score
# - Bonuses are applied before cap, but cap still limits final score
# - This ensures cannibalization always prevents high grades
# =============================================================================

# Deduction amounts (all negative)
# Why deductions are severe: These represent fundamental SEO failures that
# directly impact rankings and user experience
DEDUCTIONS = {
    # Content issues - most visible to users and search engines
    "missing_h1": -15,  # Critical basic SEO failure
    "multiple_h1": -10,  # Confuses content hierarchy  
    "heading_hierarchy_skipped": -12,  # H1→H3 breaks structure
    "title_missing": -20,  # Most critical on-page factor
    "title_too_short": -8,  # <30 chars - insufficient keyword optimization
    "title_too_long": -5,  # >60 chars - less severe than too short
    "meta_description_missing": -8,
    "meta_description_too_short": -4,  # <70 chars
    "meta_description_too_long": -3,  # >160 chars
    "duplicate_title_per_pair": -12,  # Strong cannibalization signal
    "duplicate_meta_per_pair": -6,
    "thin_content": -8,  # <300 words - insufficient depth
    "very_thin_content": -12,  # <100 words - nearly empty
    
    # Technical SEO - foundation problems
    "sitemap_missing": -8,
    "robots_txt_missing": -5,
    "no_ssl": -15,  # Security + ranking factor
    "mixed_content": -10,
    "canonical_missing": -10,  # Cannibalization enabler - critical
    "canonical_self_error": -8,
    "viewport_missing": -10,  # Mobile-first indexing requirement
    "broken_internal_link": -5,  # Per link, max -20 total
    "4xx_5xx_errors": -10,
    "doctype_missing": -10,
    "lang_missing": -5,
    "charset_missing": -5,
    "favicon_missing": -5,
    
    # Core Web Vitals - user experience metrics
    "lcp_gt_2_5": -8,  # Largest Contentful Paint > 2.5s
    "lcp_gt_4": -12,  # LCP > 4.0s (use instead of above if >4s)
    "cls_gt_0_1": -6,  # Cumulative Layout Shift > 0.1
    "cls_gt_0_25": -10,  # CLS > 0.25 (use instead of above)
    "inp_gt_200": -6,  # Interaction to Next Paint > 200ms
    "inp_gt_500": -10,  # INP > 500ms (use instead of above)
    
    # Structural issues
    "orphan_page": -10,  # No internal links pointing to page
    "images_alt_missing_50": -6,  # >50% of images missing alt tags
    "no_schema": -3,  # Nice to have, not critical
    "broken_breadcrumbs": -4,
    "no_navigation": -10,
    "no_footer": -5,
    "few_internal_links": -10,
    "noindex": -20,  # Page excluded from search engines
}

# Bonus points (positive, max +15 total)
# Why bonuses are capped: Bonuses reward excellence but can't overcome
# fundamental problems. A site with cannibalization + bonuses still can't
# exceed the cap.
BONUSES = {
    "all_cwv_pass": 5,
    "page_speed_under_1_5s": 3,
    "schema_correct": 3,
    "zero_broken_links": 2,
    "proper_heading_hierarchy": 3,
    "all_images_alt": 2,
}
BONUS_CAP = 15

# Cannibalization severity weights
# Why these weights: Different conflict types indicate different severity of
# SEO damage. Exact matches are worst (competing for identical keyword).
SEVERITY_WEIGHTS = {
    "exact_match": 1.5,  # Identical primary keyword in title
    "high_overlap": 1.25,  # >70% title/H1 similarity
    "intent_collision": 1.0,  # Different keywords, same search intent
    "url_cannibalization": 1.0,  # Similar slugs (/cheer-jackets/ vs /jackets/cheer/)
    "title_duplicate": 0.75,  # May be false positive
}

# Hard caps based on weighted conflict count
# Why caps override everything: Cannibalization fundamentally breaks SEO.
# No amount of technical perfection can overcome pages competing for the same
# keyword. The cap ensures the score reflects this reality.
CAP_TABLE = [
    (0.0, 100),   # No conflicts = no limit
    (0.5, 84),    # 0.5-1 weighted conflicts = max B (84)
    (1.5, 79),    # 1.5-2 = max C+ (79)
    (2.5, 74),    # 2.5-3 = max C (74)
    (3.5, 69),    # 3.5-4 = max D+ (69)
    (4.5, 64),    # 4.5-6 = max D (64)
    (6.5, 54),    # 6.5-9 = max D- (54)
    (10.0, 44),   # 10+ = F range (44)
]

# Page count adjustment to cap
# Why adjustment exists: Large, generally healthy sites shouldn't be destroyed
# by a few isolated conflicts. If only 1% of 500 pages have conflicts, that's
# different than 50% of 10 pages having conflicts.
PAGE_COUNT_ADJUSTMENT = [
    (20.0, 0),   # >20% of pages involved = no adjustment (widespread problem)
    (10.0, 5),   # 10-20% involved = +5 to cap
    (5.0, 10),   # 5-10% involved = +10 to cap  
    (0.0, 15),   # <5% involved = +15 to cap (isolated issue)
]

# Grade thresholds (score → grade, label, hex color)
GRADE_TABLE = [
    (95, "A+", "Excellent", "#22c55e"),
    (90, "A", "Great", "#22c55e"),
    (85, "B+", "Good", "#84cc16"),
    (80, "B", "Above Average", "#84cc16"),
    (75, "C+", "Needs Improvement", "#eab308"),
    (70, "C", "Below Average", "#eab308"),
    (65, "D+", "Poor", "#f97316"),
    (60, "D", "Serious Issues", "#f97316"),
    (50, "D-", "Critical Problems", "#ef4444"),
    (0, "F", "Failing", "#dc2626"),
]

# Grade messaging (headline, body)
GRADE_MESSAGES = {
    "A+": ("Your site is well-optimized", "Minor improvements available, but you're in great shape. Keep monitoring for new issues."),
    "A": ("Your site is well-optimized", "Minor improvements available, but you're in great shape. Keep monitoring for new issues."),
    "B+": ("Good foundation with room to grow", "Your site has solid fundamentals. Addressing the issues below will help you compete for top positions."),
    "B": ("Good foundation with room to grow", "Your site has solid fundamentals. Addressing the issues below will help you compete for top positions."),
    "C+": ("Several issues impacting performance", "Your site has problems that are likely affecting your search visibility. The fixes below should be prioritized."),
    "C": ("Several issues impacting performance", "Your site has problems that are likely affecting your search visibility. The fixes below should be prioritized."),
    "D+": ("Significant problems detected", "Your site has serious issues that are hurting your rankings. Immediate attention recommended."),
    "D": ("Significant problems detected", "Your site has serious issues that are hurting your rankings. Immediate attention recommended."),
    "D-": ("Critical issues found", "Your site is likely losing significant traffic due to these problems. These issues need to be addressed urgently."),
    "F": ("Severe problems require immediate action", "Your site has fundamental issues, including keyword cannibalization, that are actively damaging your search visibility. Without fixes, rankings will continue to suffer."),
}

# Quick wins priority scores (for sorting by impact)
QUICK_WINS_PRIORITY = {
    "cannibalization": 100,
    "missing_h1": 80,
    "title_missing": 75,
    "title_too_short": 75,
    "title_too_long": 75,
    "canonical_missing": 70,
    "canonical_self_error": 70,
    "lcp_gt_2_5": 60,
    "lcp_gt_4": 60,
    "cls_gt_0_1": 60,
    "cls_gt_0_25": 60,
    "inp_gt_200": 60,
    "inp_gt_500": 60,
    "heading_hierarchy_skipped": 50,
    "multiple_h1": 50,
    "meta_description_missing": 40,
    "meta_description_too_short": 40,
    "meta_description_too_long": 40,
}


def _calculate_score_v1_1(scanner_results: Dict[str, Any], url: str) -> Dict[str, Any]:
    """
    Apply Scoring Algorithm v1.1 to scanner results.
    
    This is the canonical scoring implementation. All score calculations
    must go through this function to ensure consistency.
    
    Args:
        scanner_results: Raw output from WebsiteScanner.scan_website()
        url: Page URL being scored
    
    Returns:
        Dict containing:
        - final_score: int (0-100)
        - grade: str (A+ to F)
        - label: str (Excellent, Good, etc.)
        - color: str (hex color for UI)
        - message: str (explanation for user)
        - headline: str (short message)
        - calculation_breakdown: dict (transparent scoring breakdown)
        - quick_wins: list (top 3-5 prioritized fixes)
        - issues: list (all issues with deductions)
        - bonuses: list (all bonuses earned)
        - cannibalization: dict (conflict details)
    """
    # Extract scanner details
    tech_details = scanner_results.get('technical_details', {})
    content_details = scanner_results.get('content_details', {})
    struct_details = scanner_results.get('structure_details', {})
    perf_details = scanner_results.get('performance_details', {})
    seo_details = scanner_results.get('seo_details', {})
    
    # STEP 1: Start with 100 points
    starting_score = 100.0
    
    # STEP 2: Count cannibalization conflicts
    # For single-page scans (lead gen), we have 0 cross-page conflicts
    # For multi-page scans, conflicts would be detected here
    weighted_conflicts = 0.0
    conflict_count = 0
    pages_in_conflicts_set = set()
    total_pages = scanner_results.get('pages_crawled', 1) or 1
    
    # STEP 3: Build issues list and apply deductions
    issues = []
    total_deductions = 0.0
    
    # Map scanner issues to deduction amounts
    # Technical issues
    tech_issues = tech_details.get('issues', [])
    tech_mapping = {
        'missing html5 doctype': ('doctype_missing', -10),
        'missing lang attribute': ('lang_missing', -5),
        'missing charset': ('charset_missing', -5),
        'missing viewport': ('viewport_missing', -10),
        'missing canonical': ('canonical_missing', -10),
        'not using https': ('no_ssl', -15),
        'missing favicon': ('favicon_missing', -5),
        'robots.txt': ('robots_txt_missing', -5),
        'sitemap not declared': ('sitemap_missing', -8),
    }
    
    for issue_text in tech_issues:
        issue_lower = issue_text.lower()
        for search_key, (issue_key, deduction) in tech_mapping.items():
            if search_key in issue_lower:
                issues.append({
                    'category': 'technical',
                    'issue_key': issue_key,
                    'issue': issue_text,
                    'deduction': deduction,
                    'url': url,
                })
                total_deductions += deduction
                break
    
    # Content issues
    content_issues = content_details.get('issues', [])
    content_mapping = {
        'missing title tag': ('title_missing', -20),
        'title tag too short': ('title_too_short', -8),
        'title tag too long': ('title_too_long', -5),
        'missing meta description': ('meta_description_missing', -8),
        'meta description too short': ('meta_description_too_short', -4),
        'meta description too long': ('meta_description_too_long', -3),
        'multiple h1 tags': ('multiple_h1', -10),
        'missing h1 tag': ('missing_h1', -15),
        'heading hierarchy skipped': ('heading_hierarchy_skipped', -12),
        'no heading structure': ('heading_hierarchy_skipped', -12),
    }
    
    for issue_text in content_issues:
        issue_lower = issue_text.lower()
        for search_key, (issue_key, deduction) in content_mapping.items():
            if search_key in issue_lower:
                issues.append({
                    'category': 'content',
                    'issue_key': issue_key,
                    'issue': issue_text,
                    'deduction': deduction,
                    'url': url,
                })
                total_deductions += deduction
                break
    
    # Word count deductions (thin content)
    word_count = content_details.get('word_count', 0) or 0
    if word_count < 100:
        issues.append({
            'category': 'content',
            'issue_key': 'very_thin_content',
            'issue': 'Very thin content (under 100 words)',
            'deduction': -12,
            'url': url,
        })
        total_deductions += -12
    elif word_count < 300:
        issues.append({
            'category': 'content',
            'issue_key': 'thin_content',
            'issue': 'Content under 300 words',
            'deduction': -8,
            'url': url,
        })
        total_deductions += -8
    
    # Structure issues
    struct_issues = struct_details.get('issues', [])
    struct_mapping = {
        'no navigation': ('no_navigation', -10),
        'no footer': ('no_footer', -5),
        'no structured data': ('no_schema', -3),
        'very few internal links': ('few_internal_links', -10),
    }
    
    for issue_text in struct_issues:
        issue_lower = issue_text.lower()
        for search_key, (issue_key, deduction) in struct_mapping.items():
            if search_key in issue_lower:
                issues.append({
                    'category': 'structure',
                    'issue_key': issue_key,
                    'issue': issue_text,
                    'deduction': deduction,
                    'url': url,
                })
                total_deductions += deduction
                break
    
    # SEO issues (noindex is critical)
    seo_issues = seo_details.get('issues', [])
    for issue_text in seo_issues:
        if 'noindex' in issue_text.lower():
            issues.append({
                'category': 'seo',
                'issue_key': 'noindex',
                'issue': issue_text,
                'deduction': -20,
                'url': url,
            })
            total_deductions += -20
            break
    
    # Score after deductions
    score_after_deductions = starting_score + total_deductions  # total_deductions is negative
    
    # STEP 4: Calculate bonuses (max +15 total)
    # Bonuses reward excellence but are capped to prevent them from
    # masking fundamental problems
    bonuses = []
    total_bonuses = 0.0
    
    # Page speed bonus
    response_time_ms = perf_details.get('response_time_ms', 9999)
    if response_time_ms < 1500:
        bonuses.append({'key': 'page_speed_under_1_5s', 'bonus': 3, 'label': 'Page speed <1.5s'})
        total_bonuses += 3
    
    # Schema bonus
    if struct_details.get('has_schema'):
        bonuses.append({'key': 'schema_correct', 'bonus': 3, 'label': 'Schema markup implemented'})
        total_bonuses += 3
    
    # Heading hierarchy bonus
    has_hierarchy = content_details.get('has_heading_structure', False)
    hierarchy_issue = any('hierarchy' in str(i).lower() for i in content_issues)
    if has_hierarchy and not hierarchy_issue:
        bonuses.append({'key': 'proper_heading_hierarchy', 'bonus': 3, 'label': 'Proper heading hierarchy'})
        total_bonuses += 3
    
    # Alt tags bonus
    alt_coverage = content_details.get('alt_text_coverage', 0)
    if alt_coverage >= 100:
        bonuses.append({'key': 'all_images_alt', 'bonus': 2, 'label': 'All images have alt tags'})
        total_bonuses += 2
    
    # Cap bonuses at +15
    total_bonuses = min(total_bonuses, BONUS_CAP)
    score_before_cap = score_after_deductions + total_bonuses
    
    # STEP 5: Determine cannibalization cap
    # Find the maximum score allowed based on weighted conflict count
    cannibalization_cap = 100
    for threshold, max_score in reversed(CAP_TABLE):
        if weighted_conflicts >= threshold:
            cannibalization_cap = max_score
            break
    
    # STEP 6: Apply page count adjustment
    # Calculate % of pages involved in conflicts
    pages_in_conflicts_count = len(pages_in_conflicts_set)
    pct_in_conflicts = (pages_in_conflicts_count / total_pages * 100.0) if total_pages > 0 else 0
    
    page_count_adjustment = 0
    for pct_threshold, adjustment in PAGE_COUNT_ADJUSTMENT:
        if pct_in_conflicts > pct_threshold:
            page_count_adjustment = adjustment
            break
    
    # Adjusted cap (never exceeds 100)
    adjusted_cap = min(100, cannibalization_cap + page_count_adjustment)
    
    # Apply cap (can only lower score, never raise it)
    cap_applied = score_before_cap > adjusted_cap
    if weighted_conflicts > 0:
        score_after_cap = min(score_before_cap, adjusted_cap)
    else:
        # No conflicts = no cap applies
        score_after_cap = score_before_cap
    
    # STEP 7: Floor at 0, ceiling at 100
    final_score = max(0.0, min(100.0, score_after_cap))
    final_score = round(final_score)
    
    # STEP 8: Assign grade, label, color
    grade = "F"
    label = "Failing"
    color = "#dc2626"
    for min_score, g, lbl, clr in GRADE_TABLE:
        if final_score >= min_score:
            grade = g
            label = lbl
            color = clr
            break
    
    # Get message for grade
    headline, message = GRADE_MESSAGES.get(grade, ("", ""))
    
    # STEP 9: Build quick wins (top 3-5 prioritized fixes)
    quick_wins = []
    
    # Cannibalization always #1 if present
    if conflict_count > 0:
        quick_wins.append({
            "priority": 1,
            "issue": "Keyword Cannibalization",
            "description": f"{conflict_count} page pair(s) competing for similar keywords",
            "recommendation": "Consolidate or differentiate page targeting",
            "impact": "High",
        })
    
    # Sort remaining issues by priority score
    def get_priority_score(issue):
        return QUICK_WINS_PRIORITY.get(issue.get('issue_key', ''), 30)
    
    sorted_issues = sorted(issues, key=get_priority_score, reverse=True)
    idx = len(quick_wins) + 1
    for issue in sorted_issues[:5 - len(quick_wins)]:
        if idx > 5:
            break
        quick_wins.append({
            "priority": idx,
            "issue": issue.get('issue', 'Issue'),
            "description": issue.get('issue', ''),
            "recommendation": _get_recommendation_for_issue(issue.get('issue_key', '')),
            "impact": "High" if abs(issue.get('deduction', 0)) >= 15 else "Medium",
        })
        idx += 1
    
    # Build category breakdown (diagnostic only, doesn't affect main score)
    categories = _build_category_breakdown(
        tech_details, content_details, struct_details,
        perf_details, seo_details, conflict_count
    )
    
    return {
        "final_score": final_score,
        "grade": grade,
        "label": label,
        "color": color,
        "message": message,
        "headline": headline,
        "calculation_breakdown": {
            "starting_score": int(starting_score),
            "total_deductions": int(round(total_deductions)),
            "total_bonuses": int(round(total_bonuses)),
            "score_before_cap": int(round(score_before_cap)),
            "cannibalization_cap": cannibalization_cap,
            "page_count_adjustment": page_count_adjustment,
            "adjusted_cap": adjusted_cap,
            "cap_applied": cap_applied,
        },
        "issues": issues,
        "bonuses": bonuses,
        "quick_wins": quick_wins,
        "cannibalization": {
            "conflict_count": conflict_count,
            "weighted_conflict_count": round(weighted_conflicts, 2),
            "conflicts": [],  # Empty for single-page scans
        },
        "categories": categories,
    }


def _get_recommendation_for_issue(issue_key: str) -> str:
    """Get actionable recommendation for issue key"""
    recommendations = {
        "missing_h1": "Add a single H1 tag containing primary keyword",
        "multiple_h1": "Keep only one H1 tag per page",
        "title_missing": "Add a title tag (30-60 characters with primary keyword)",
        "title_too_short": "Expand title to 30-60 characters with primary keyword",
        "title_too_long": "Shorten title to 30-60 characters",
        "meta_description_missing": "Add meta description (70-160 characters)",
        "meta_description_too_short": "Expand meta description to 70-160 characters",
        "canonical_missing": "Add canonical link tag to prevent duplicate content",
        "no_ssl": "Enable SSL/TLS and redirect HTTP to HTTPS",
        "viewport_missing": "Add viewport meta tag for mobile optimization",
        "sitemap_missing": "Create and submit XML sitemap",
        "no_schema": "Implement JSON-LD structured data",
        "thin_content": "Add more content (at least 300 words)",
        "very_thin_content": "Add substantial content (at least 300 words)",
        "heading_hierarchy_skipped": "Fix heading hierarchy (don't skip levels)",
        "no_navigation": "Add navigation structure to site",
        "few_internal_links": "Add internal links to improve site structure",
        "noindex": "Remove noindex directive to allow search engine indexing",
    }
    return recommendations.get(issue_key, "Address this issue to improve SEO")


def _build_category_breakdown(
    tech_details: Dict,
    content_details: Dict,
    struct_details: Dict,
    perf_details: Dict,
    seo_details: Dict,
    conflict_count: int,
) -> Dict[str, Dict[str, int]]:
    """
    Build diagnostic category scores (0-100 each) for UI display.
    These scores are independent of the main score calculation and serve
    as a visual breakdown for the user.
    """
    # Technical Score (100 points possible)
    tech_score = 100
    if not tech_details.get("has_sitemap", False):
        tech_score -= 15
    if not tech_details.get("has_robots_txt", False):
        tech_score -= 10
    if not tech_details.get("is_https", False):
        tech_score -= 20
    if not tech_details.get("has_canonical", False):
        tech_score -= 20
    if not tech_details.get("has_viewport", False):
        tech_score -= 15
    tech_score = max(0, tech_score)
    
    # Content Score (100 points possible)
    content_score = 100
    if not content_details.get("has_h1", False):
        content_score -= 25
    elif (content_details.get("h1_count") or 1) > 1:
        content_score -= 15
    if not content_details.get("has_heading_structure", False):
        content_score -= 20
    if not content_details.get("has_title", False):
        content_score -= 25
    elif not (30 <= len(content_details.get("title", "")) <= 60):
        content_score -= 15
    if not content_details.get("has_meta_description", False):
        content_score -= 15
    if (content_details.get("word_count") or 0) < 300:
        content_score -= 15
    content_score = max(0, content_score)
    
    # Structure Score (100 points possible)
    structure_score = 100
    internal_links = struct_details.get("internal_links", 0)
    if internal_links == 0:
        structure_score -= 50
    elif internal_links < 5:
        structure_score -= 25
    if not struct_details.get("has_navigation", False):
        structure_score -= 25
    if not struct_details.get("has_schema", False):
        structure_score -= 25
    structure_score = max(0, structure_score)
    
    # Performance Score (100 points possible)
    performance_score = 100
    response_time = perf_details.get("response_time_ms", 0)
    if response_time > 3000:
        performance_score -= 35
    elif response_time > 2000:
        performance_score -= 20
    page_size = perf_details.get("page_size_kb", 0)
    if page_size > 2000:
        performance_score -= 25
    if not perf_details.get("has_compression", False):
        performance_score -= 15
    performance_score = max(0, performance_score)
    
    # SEO Score (100 points possible)
    # Cannibalization is weighted heavily (50 pts for zero conflicts)
    seo_score = 100
    if conflict_count > 0:
        seo_score -= min(50, conflict_count * 15)
    if not content_details.get("has_title", False):
        seo_score -= 15
    if not content_details.get("has_meta_description", False):
        seo_score -= 10
    if not tech_details.get("has_canonical", False):
        seo_score -= 15
    if not struct_details.get("has_schema", False):
        seo_score -= 10
    seo_score = max(0, seo_score)
    
    return {
        "technical": {"score": tech_score, "max": 100},
        "content": {"score": content_score, "max": 100},
        "structure": {"score": structure_score, "max": 100},
        "performance": {"score": performance_score, "max": 100},
        "seo": {"score": seo_score, "max": 100},
    }


async def _run_scan(scan_id: UUID, url: str, scan_type: str):
    """Background task to run the actual scan"""
    from app.core.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            # Update scan status to processing
            scan = await db.get(Scan, scan_id)
            if not scan:
                return
            
            scan.status = 'processing'
            scan.started_at = datetime.now()
            await db.commit()
            
            # Run scanner
            async with WebsiteScanner() as scanner:
                results = await scanner.scan_website(str(url), scan_type)
            
            # ==================================================================
            # APPLY SCORING ALGORITHM v1.1
            # Replace scanner's simple weighted average with canonical algorithm
            # ==================================================================
            scoring_result = _calculate_score_v1_1(results, str(url))
            
            # Override scanner scores with algorithm output
            results['overall_score'] = float(scoring_result['final_score'])
            results['grade'] = scoring_result['grade']
            
            # Store algorithm metadata for API response
            results['score_label'] = scoring_result['label']
            results['score_color'] = scoring_result['color']
            results['score_message'] = scoring_result['message']
            results['score_headline'] = scoring_result['headline']
            results['calculation_breakdown'] = scoring_result['calculation_breakdown']
            results['quick_wins'] = scoring_result['quick_wins']
            results['cannibalization'] = scoring_result['cannibalization']
            
            # Update category scores from diagnostic breakdown
            categories = scoring_result['categories']
            results['technical_score'] = float(categories['technical']['score'])
            results['content_score'] = float(categories['content']['score'])
            results['structure_score'] = float(categories['structure']['score'])
            results['performance_score'] = float(categories['performance']['score'])
            results['seo_score'] = float(categories['seo']['score'])
            
            # Build recommendations from scorer issues (with deduction amounts)
            recommendations = []
            for issue in scoring_result['issues']:
                recommendations.append({
                    'category': issue.get('category', 'content').capitalize(),
                    'priority': 'high' if abs(issue.get('deduction', 0)) >= 15 else 'medium',
                    'issue': issue.get('issue', 'Issue detected'),
                    'action': _get_recommendation_for_issue(issue.get('issue_key', '')),
                    'deduction': issue.get('deduction'),
                })
            results['recommendations'] = recommendations[:15]  # Limit to 15
            # ==================================================================
            
            # Update scan with results
            scan = await db.get(Scan, scan_id)  # Refresh to avoid detached instance
            if not scan:
                return
                
            scan.status = results['status']
            scan.overall_score = results.get('overall_score')
            scan.grade = results.get('grade')
            scan.technical_score = results.get('technical_score')
            scan.content_score = results.get('content_score')
            scan.structure_score = results.get('structure_score')
            scan.performance_score = results.get('performance_score')
            scan.seo_score = results.get('seo_score')
            
            # Store scoring metadata in JSONB fields (Algorithm v1.1)
            tech_details = results.get('technical_details') or {}
            content_details = results.get('content_details') or {}
            struct_details = results.get('structure_details') or {}
            perf_details = results.get('performance_details') or {}
            seo_details = results.get('seo_details') or {}
            
            scan.technical_details = {
                **tech_details,
                'calculation_breakdown': results.get('calculation_breakdown')
            }
            scan.content_details = {
                **content_details,
                'score_display': {
                    'label': results.get('score_label'),
                    'color': results.get('score_color'),
                    'message': results.get('score_message'),
                    'headline': results.get('score_headline'),
                }
            }
            scan.structure_details = {
                **struct_details,
                'quick_wins': results.get('quick_wins')
            }
            scan.performance_details = {
                **perf_details,
                'categories': results.get('categories')
            }
            scan.seo_details = {
                **seo_details,
                'cannibalization': results.get('cannibalization')
            }
            
            scan.recommendations = results.get('recommendations', [])
            scan.pages_crawled = results.get('pages_crawled', 0)
            scan.scan_duration_seconds = results.get('scan_duration_seconds')
            scan.completed_at = datetime.now()
            
            if results.get('error_message'):
                scan.error_message = results['error_message']
            
            await db.commit()
            
        except Exception as e:
            # Update scan with error
            scan = await db.get(Scan, scan_id)
            if scan:
                scan.status = 'failed'
                scan.error_message = str(e)
                scan.completed_at = datetime.now()
                await db.commit()


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new website scan.
    
    The scan will run in the background. Use GET /scans/{scan_id} to check status.
    """
    # Extract domain from URL
    parsed_url = urlparse(str(request.url))
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Verify site_id if provided
    site = None
    if request.site_id:
        site = await db.get(Site, request.site_id)
        if not site:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Site not found"
            )
    
    # Create scan record
    scan = Scan(
        site_id=request.site_id,
        url=str(request.url),
        domain=domain,
        scan_type=request.scan_type,
        status='pending',
    )
    
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    
    # Start background scan
    background_tasks.add_task(_run_scan, scan.id, request.url, request.scan_type)
    
    return ScanResponse(
        id=scan.id,
        url=scan.url,
        domain=scan.domain,
        scan_type=scan.scan_type,
        status=scan.status,
        overall_score=scan.overall_score,
        grade=scan.grade,
        technical_score=scan.technical_score,
        content_score=scan.content_score,
        structure_score=scan.structure_score,
        performance_score=scan.performance_score,
        seo_score=scan.seo_score,
        technical_details=scan.technical_details or {},
        content_details=scan.content_details or {},
        structure_details=scan.structure_details or {},
        performance_details=scan.performance_details or {},
        seo_details=scan.seo_details or {},
        recommendations=scan.recommendations or [],
        pages_crawled=scan.pages_crawled,
        scan_duration_seconds=scan.scan_duration_seconds,
        error_message=scan.error_message,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
    )


@router.get("/{scan_id}/report", response_model=ScanReportResponse)
async def get_scan_report(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full lead-gen report for a scan (Keyword Cannibalization Report).
    No authentication required. Used by WordPress plugin "Get Full Report" CTA.
    """
    scan = await db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )
    recommendations = scan.recommendations or []
    content_details = scan.content_details or {}
    structure_details = scan.structure_details or {}
    pages_crawled = scan.pages_crawled or 0
    url = scan.url or ""

    # Cannibalization-style conflicts derived from Content/Structure recommendations
    content_issues = content_details.get("issues", [])
    structure_issues = structure_details.get("issues", [])
    content_recs = [r for r in recommendations if (r.get("category") or "").lower() == "content"]
    structure_recs = [r for r in recommendations if (r.get("category") or "").lower() == "structure"]
    conflict_count = len(content_recs) + len(structure_recs)
    if conflict_count == 0:
        conflict_count = len(content_issues) + len(structure_issues)
    if conflict_count == 0 and recommendations:
        conflict_count = min(len(recommendations), 5)

    # Overall risk level from score and conflict count
    score = scan.overall_score or 0
    if conflict_count >= 5 or score < 50:
        risk_level = "High"
    elif conflict_count >= 2 or score < 70:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # Build keyword cannibalization list from content/structure issues and recommendations
    keyword_details: List[dict] = []
    seen_keys: set = set()
    for rec in recommendations:
        cat = (rec.get("category") or "").lower()
        if cat not in ("content", "structure"):
            continue
        issue = (rec.get("issue") or "Keyword conflict").strip()
        if not issue or issue in seen_keys:
            continue
        seen_keys.add(issue)
        keyword_name = issue[:80] if len(issue) > 80 else issue
        severity = "High" if (rec.get("priority") or "").lower() == "high" else "Medium"
        keyword_details.append({
            "keyword": keyword_name,
            "conflicting_urls": [url] if url else [],
            "conflict_type": "same intent" if cat == "content" else "same keyword",
            "severity": severity,
        })
    for issue in (content_issues + structure_issues)[:5]:
        issue_str = (issue if isinstance(issue, str) else str(issue)).strip()[:80]
        if issue_str and issue_str not in seen_keys:
            seen_keys.add(issue_str)
            keyword_details.append({
                "keyword": issue_str,
                "conflicting_urls": [url] if url else [],
                "conflict_type": "same intent",
                "severity": "Medium",
            })

    if not keyword_details and conflict_count > 0:
        keyword_details = [{
            "keyword": "Multiple pages competing for similar topics",
            "conflicting_urls": [url] if url else [],
            "conflict_type": "same intent",
            "severity": "High" if risk_level == "High" else "Medium",
        }]

    summary = ScanReportSummary(
        website_url=url,
        total_pages_analyzed=pages_crawled,
        total_cannibalization_conflicts=conflict_count,
        overall_risk_level=risk_level,
    )
    educational = {
        "title": "What is keyword cannibalization?",
        "body": "Keyword cannibalization occurs when multiple pages on your site target the same or very similar keywords. Search engines may split rankings between these pages or pick the wrong one, which hurts your visibility and traffic. Consolidating or clearly differentiating content helps you rank better and gives users a clearer path.",
    }
    locked = [
        "Page consolidation",
        "Primary keyword assignment",
        "Content silo restructuring",
    ]
    upgrade_cta = {
        "label": "Unlock Full Report & Fix Issues",
        "scan_id_param": "scan_id",
    }

    return ScanReportResponse(
        scan_id=scan.id,
        scan_summary=summary,
        keyword_cannibalization_details=[KeywordCannibalizationItem(**k) for k in keyword_details],
        educational_explanation=educational,
        locked_recommendations=locked,
        upgrade_cta=upgrade_cta,
    )


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get scan results by ID (with Algorithm v1.1 metadata)"""
    scan = await db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    # Extract scoring metadata from JSONB fields
    tech = scan.technical_details or {}
    content = scan.content_details or {}
    struct = scan.structure_details or {}
    perf = scan.performance_details or {}
    seo = scan.seo_details or {}
    
    # Build score object (Algorithm v1.1)
    score_obj = None
    if content.get("score_display"):
        sd = content["score_display"]
        score_obj = {
            "final": int(scan.overall_score) if scan.overall_score is not None else 0,
            "grade": scan.grade or "F",
            "label": sd.get("label"),
            "color": sd.get("color"),
            "message": sd.get("message"),
            "headline": sd.get("headline"),
        }
    
    return ScanResponse(
        id=scan.id,
        url=scan.url,
        domain=scan.domain,
        scan_type=scan.scan_type,
        status=scan.status,
        overall_score=scan.overall_score,
        grade=scan.grade,
        technical_score=scan.technical_score,
        content_score=scan.content_score,
        structure_score=scan.structure_score,
        performance_score=scan.performance_score,
        seo_score=scan.seo_score,
        technical_details={k: v for k, v in tech.items() if k != "calculation_breakdown"},
        content_details={k: v for k, v in content.items() if k != "score_display"},
        structure_details={k: v for k, v in struct.items() if k != "quick_wins"},
        performance_details={k: v for k, v in perf.items() if k != "categories"},
        seo_details={k: v for k, v in seo.items() if k != "cannibalization"},
        recommendations=scan.recommendations or [],
        pages_crawled=scan.pages_crawled or 0,
        scan_duration_seconds=scan.scan_duration_seconds,
        error_message=scan.error_message,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
        score=score_obj,
        calculation_breakdown=tech.get("calculation_breakdown"),
        quick_wins=struct.get("quick_wins"),
        categories=perf.get("categories"),
        cannibalization=seo.get("cannibalization"),
    )


@router.get("", response_model=List[ScanSummary])
async def list_scans(
    domain: Optional[str] = None,
    site_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    List scans with optional filters.
    
    Query parameters:
    - domain: Filter by domain
    - site_id: Filter by site ID
    - status: Filter by status (pending, processing, completed, failed)
    - limit: Number of results (default: 20)
    - offset: Pagination offset (default: 0)
    """
    query = select(Scan)
    
    if domain:
        query = query.where(Scan.domain == domain)
    if site_id:
        query = query.where(Scan.site_id == site_id)
    if status_filter:
        query = query.where(Scan.status == status_filter)
    
    query = query.order_by(desc(Scan.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    scans = result.scalars().all()
    
    return [
        ScanSummary(
            id=scan.id,
            url=scan.url,
            domain=scan.domain,
            status=scan.status,
            overall_score=scan.overall_score,
            grade=scan.grade,
            created_at=scan.created_at,
            completed_at=scan.completed_at,
        )
        for scan in scans
    ]


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a scan"""
    scan = await db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    await db.delete(scan)
    await db.commit()
    
    return None
