"""
2025 SEO Alignment: Mobile-First Rendering Validation (Core Web Vitals)

Google has effectively shifted to a "mobile-only" world. This module validates
Core Web Vitals before publishing to ensure mobile performance is locked in.
"""
import re
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Page
from app.types import GateCheckResult
from app.core.config import settings


class CoreWebVitalsValidator:
    """
    Validates Core Web Vitals for mobile-first rendering.
    
    Checks:
    - Cumulative Layout Shift (CLS) - Layout stability
    - Largest Contentful Paint (LCP) - Loading performance
    - First Input Delay (FID) - Interactivity (estimated from content structure)
    - Mobile viewport configuration
    - Image optimization hints
    """
    
    def __init__(self):
        from app.core.config import settings
        # Core Web Vitals thresholds (Google's recommended values)
        self.CLS_THRESHOLD = settings.cls_threshold  # Good: < 0.1, Needs Improvement: 0.1-0.25, Poor: > 0.25
        self.LCP_THRESHOLD = settings.lcp_threshold  # Good: < 2.5s, Needs Improvement: 2.5-4.0s, Poor: > 4.0s
        self.FID_THRESHOLD = settings.fid_threshold  # Good: < 100ms, Needs Improvement: 100-300ms, Poor: > 300ms
        
        # These are estimated from content structure
        # Real metrics would come from actual page rendering
        self.estimated_cls = 0.0
        self.estimated_lcp = 0.0
        self.estimated_fid = 0.0
    
    async def validate_web_vitals(
        self,
        page: Page,
        db: AsyncSession,
    ) -> GateCheckResult:
        """
        Validate Core Web Vitals for mobile-first rendering.
        
        Note: This performs static analysis of content structure.
        Real metrics would require actual page rendering and measurement.
        
        Args:
            page: Page to validate
            db: Database session
            
        Returns:
            GateCheckResult with passed status and details
        """
        if not page.body:
            return {
                "passed": False,
                "reason": "No content body to validate web vitals",
                "details": {"body_exists": False},
            }
        
        body = page.body
        body_lower = body.lower()
        
        issues = []
        warnings = []
        details = {}
        
        # Check 1: Mobile viewport meta tag (inferred from content structure)
        # In a real implementation, this would check the actual HTML
        # For now, we check if content suggests mobile-friendly structure
        has_mobile_structure = (
            len(body) < 100000  # Not excessively long
            and not bool(re.search(r'<table[^>]*width[^>]*>', body_lower))  # No fixed-width tables
            and not bool(re.search(r'width\s*=\s*["\']\d+', body_lower))  # No fixed widths
        )
        
        if not has_mobile_structure:
            warnings.append("Content may not be mobile-optimized (check for fixed widths)")
        
        details["has_mobile_structure"] = has_mobile_structure
        
        # Check 2: Image optimization (estimate CLS impact)
        # Images without dimensions or lazy loading can cause layout shift
        image_patterns = [
            r'<img[^>]*>',
            r'!\[.*?\]\(.*?\)',  # Markdown images
        ]
        
        image_count = 0
        images_without_dimensions = 0
        images_without_lazy = 0
        
        for pattern in image_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            image_count += len(matches)
            
            for match in matches:
                if 'width' not in match.lower() and 'height' not in match.lower():
                    images_without_dimensions += 1
                if 'loading' not in match.lower() or 'lazy' not in match.lower():
                    images_without_lazy += 1
        
        # Estimate CLS based on images without dimensions
        estimated_cls = min(0.3, (images_without_dimensions * 0.05))
        
        if estimated_cls > self.CLS_THRESHOLD:
            issues.append(
                f"Estimated CLS ({estimated_cls:.2f}) exceeds threshold ({self.CLS_THRESHOLD})"
            )
        
        details["image_count"] = image_count
        details["images_without_dimensions"] = images_without_dimensions
        details["images_without_lazy"] = images_without_lazy
        details["estimated_cls"] = estimated_cls
        
        # Check 3: Content length and structure (estimate LCP)
        # Longer content with many resources can delay LCP
        content_length = len(body)
        resource_count = (
            image_count
            + len(re.findall(r'<script[^>]*>', body_lower))
            + len(re.findall(r'<link[^>]*rel\s*=\s*["\']stylesheet', body_lower))
        )
        
        # Estimate LCP based on content size and resources
        # This is a rough estimate; real LCP requires actual rendering
        estimated_lcp = min(5.0, 1.0 + (content_length / 50000) + (resource_count * 0.2))
        
        if estimated_lcp > self.LCP_THRESHOLD:
            warnings.append(
                f"Estimated LCP ({estimated_lcp:.2f}s) may exceed threshold ({self.LCP_THRESHOLD}s)"
            )
        
        details["content_length"] = content_length
        details["resource_count"] = resource_count
        details["estimated_lcp"] = estimated_lcp
        
        # Check 4: JavaScript and interactivity (estimate FID)
        # Heavy JavaScript can delay interactivity
        script_count = len(re.findall(r'<script[^>]*>', body_lower))
        inline_scripts = len(re.findall(r'<script[^>]*>.*?</script>', body, re.DOTALL | re.IGNORECASE))
        
        # Estimate FID based on script usage
        estimated_fid = min(300.0, 50.0 + (script_count * 10) + (inline_scripts * 20))
        
        if estimated_fid > self.FID_THRESHOLD:
            warnings.append(
                f"Estimated FID ({estimated_fid:.0f}ms) may exceed threshold ({self.FID_THRESHOLD}ms)"
            )
        
        details["script_count"] = script_count
        details["inline_scripts"] = inline_scripts
        details["estimated_fid"] = estimated_fid
        
        # Check 5: Font loading and text rendering
        # Web fonts can cause FOIT/FOUT (Flash of Invisible/Unstyled Text)
        font_usage = bool(re.search(r'@font-face|font-family|google.*font', body_lower))
        
        if font_usage:
            warnings.append("Custom fonts detected - ensure font-display: swap for better CLS")
        
        details["font_usage"] = font_usage
        
        # Overall assessment
        # Block publishing only if CLS is definitely problematic
        # LCP and FID are warnings since they require actual rendering to measure accurately
        passed = estimated_cls <= self.CLS_THRESHOLD
        
        if not passed:
            return {
                "passed": False,
                "reason": f"Core Web Vitals validation failed: {issues[0] if issues else 'CLS threshold exceeded'}",
                "details": details,
                "warnings": warnings,
            }
        
        # Passed, but may have warnings
        return {
            "passed": True,
            "details": details,
            "warnings": warnings if warnings else None,
        }
    
    def get_web_vitals_recommendations(self, details: Dict[str, Any]) -> List[str]:
        """
        Get recommendations for improving Core Web Vitals.
        
        Args:
            details: Validation details from validate_web_vitals
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if details.get("images_without_dimensions", 0) > 0:
            recommendations.append(
                f"Add width and height attributes to {details['images_without_dimensions']} images to prevent CLS"
            )
        
        if details.get("images_without_lazy", 0) > 0:
            recommendations.append(
                f"Add loading='lazy' to {details['images_without_lazy']} images for better performance"
            )
        
        if details.get("estimated_lcp", 0) > self.LCP_THRESHOLD:
            recommendations.append(
                "Optimize images and reduce resource count to improve LCP"
            )
        
        if details.get("estimated_fid", 0) > self.FID_THRESHOLD:
            recommendations.append(
                "Reduce JavaScript execution time to improve FID"
            )
        
        return recommendations

