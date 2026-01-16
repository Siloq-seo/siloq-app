"""
2025 SEO Alignment: First-Hand Experience Verification

Google now heavily favors content that demonstrates "real-world experience" and
"editorial authority" over generic AI-generated information. This module enforces
proof of experience requirements for supporting pages.
"""
import re
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Page
from app.types import GateCheckResult


class ExperienceVerifier:
    """
    Verifies that content demonstrates first-hand experience.
    
    Checks for:
    - Specific data points, statistics, or metrics
    - Case studies or real-world examples
    - First-hand anecdotes or personal experiences
    - Concrete evidence rather than generic statements
    """
    
    # Patterns that indicate first-hand experience
    EXPERIENCE_INDICATORS = [
        r'\b(?:we|I|our team|our company|we found|we tested|we measured|we observed)\b',
        r'\b(?:case study|case studies|real example|real-world|actual data|measured|tested|observed)\b',
        r'\b(?:according to our|based on our|from our|our research|our data|our analysis)\b',
        r'\b(?:%|percent|percentage|\d+%|\d+ out of|\d+ of \d+)\b',  # Statistics
        r'\b(?:in \d{4}|last year|this year|recently|over the past)\b',  # Time-specific
        r'\b(?:customer|client|user|participant|respondent)\b',  # Real entities
    ]
    
    # Patterns that indicate generic/AI-generated content (negative signals)
    GENERIC_INDICATORS = [
        r'\b(?:many people|some experts|it is said|generally speaking|in general)\b',
        r'\b(?:could be|might be|possibly|perhaps|maybe)\b',  # Vague language
        r'\b(?:always|never|everyone|nobody)\b',  # Absolute statements without evidence
    ]
    
    def __init__(self):
        from app.core.config import settings
        self.min_experience_indicators = settings.min_experience_indicators
        self.max_generic_indicators = settings.max_generic_indicators
    
    async def verify_experience(
        self,
        page: Page,
    ) -> GateCheckResult:
        """
        Verify that content demonstrates first-hand experience.
        
        Args:
            page: Page to verify
            
        Returns:
            GateCheckResult with passed status and details
        """
        if not page.body:
            return {
                "passed": False,
                "reason": "No content body to verify experience",
                "details": {"body_exists": False},
            }
        
        body_lower = page.body.lower()
        
        # Count experience indicators
        experience_count = 0
        found_indicators = []
        
        for pattern in self.EXPERIENCE_INDICATORS:
            matches = re.findall(pattern, body_lower, re.IGNORECASE)
            if matches:
                experience_count += len(matches)
                found_indicators.append({
                    "pattern": pattern,
                    "matches": len(matches),
                })
        
        # Count generic indicators
        generic_count = 0
        found_generic = []
        
        for pattern in self.GENERIC_INDICATORS:
            matches = re.findall(pattern, body_lower, re.IGNORECASE)
            if matches:
                generic_count += len(matches)
                found_generic.append({
                    "pattern": pattern,
                    "matches": len(matches),
                })
        
        # Check for specific data points (numbers, percentages, dates)
        data_points = re.findall(r'\b\d+(?:\.\d+)?%?\b', page.body)
        has_data = len(data_points) >= 2
        
        # Check for case studies or examples
        has_examples = bool(re.search(
            r'\b(?:case study|example|instance|illustration|scenario)\b',
            body_lower,
            re.IGNORECASE
        ))
        
        # Determine if experience is verified
        passed = (
            experience_count >= self.min_experience_indicators
            and generic_count <= self.max_generic_indicators
            and (has_data or has_examples)
        )
        
        if not passed:
            reasons = []
            if experience_count < self.min_experience_indicators:
                reasons.append(
                    f"Insufficient experience indicators ({experience_count}/{self.min_experience_indicators} required)"
                )
            if generic_count > self.max_generic_indicators:
                reasons.append(
                    f"Too many generic indicators ({generic_count}/{self.max_generic_indicators} max allowed)"
                )
            if not has_data and not has_examples:
                reasons.append("Missing specific data points or examples")
            
            return {
                "passed": False,
                "reason": "; ".join(reasons),
                "details": {
                    "experience_indicators": experience_count,
                    "generic_indicators": generic_count,
                    "data_points": len(data_points),
                    "has_examples": has_examples,
                    "found_indicators": found_indicators[:5],  # Limit to first 5
                    "found_generic": found_generic[:5],
                },
            }
        
        return {
            "passed": True,
            "details": {
                "experience_indicators": experience_count,
                "generic_indicators": generic_count,
                "data_points": len(data_points),
                "has_examples": has_examples,
                "score": min(1.0, experience_count / 5.0),  # Normalized score
            },
        }

