"""
2025 SEO Alignment: GEO (Generative Engine Optimization) Formatting

Google's AI Overviews and AI Mode require content to be "citation-ready" for AI systems.
This module enforces formatting that makes content easily scraped and cited by LLMs.
"""
import re
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Page
from app.types import GateCheckResult


class GEOFormatter:
    """
    Validates that content is formatted for Generative Engine Optimization (GEO).
    
    Requirements:
    - Direct answer at the top of content (first 200 characters)
    - Concise bullet points for key information
    - Clear section headers (H2/H3)
    - Structured data format (lists, tables where appropriate)
    - FAQ section with direct answers
    """
    
    def __init__(self):
        from app.core.config import settings
        self.direct_answer_max_chars = settings.direct_answer_max_chars
        self.min_bullet_points = settings.min_bullet_points
        self.min_headings = settings.min_headings
    
    async def validate_geo_formatting(
        self,
        page: Page,
    ) -> GateCheckResult:
        """
        Validate that content is formatted for GEO (AI citation-ready).
        
        Args:
            page: Page to validate
            
        Returns:
            GateCheckResult with passed status and details
        """
        if not page.body:
            return {
                "passed": False,
                "reason": "No content body to validate GEO formatting",
                "details": {"body_exists": False},
            }
        
        body = page.body
        body_lower = body.lower()
        
        issues = []
        details = {}
        
        # Check 1: Direct answer at the top
        first_paragraph = body.split('\n\n')[0] if '\n\n' in body else body[:500]
        first_200_chars = first_paragraph[:self.direct_answer_max_chars]
        
        # Direct answer should be a complete sentence that answers the question
        has_direct_answer = (
            len(first_200_chars) >= 50  # Substantial enough
            and '.' in first_200_chars  # Complete sentence
            and not first_200_chars.strip().startswith('#')  # Not just a heading
        )
        
        if not has_direct_answer:
            issues.append(
                f"Missing direct answer in first {self.direct_answer_max_chars} characters"
            )
        
        details["has_direct_answer"] = has_direct_answer
        details["first_200_chars"] = first_200_chars[:200]
        
        # Check 2: Bullet points or lists
        bullet_patterns = [
            r'^\s*[-*•]\s+',  # Markdown bullets
            r'^\s*\d+\.\s+',  # Numbered lists
            r'<li>',  # HTML lists
        ]
        
        bullet_count = 0
        for pattern in bullet_patterns:
            matches = re.findall(pattern, body, re.MULTILINE)
            bullet_count += len(matches)
        
        if bullet_count < self.min_bullet_points:
            issues.append(
                f"Insufficient bullet points ({bullet_count}/{self.min_bullet_points} required)"
            )
        
        details["bullet_points"] = bullet_count
        
        # Check 3: Section headings (H2/H3)
        heading_patterns = [
            r'^##\s+',  # Markdown H2
            r'^###\s+',  # Markdown H3
            r'<h2>',  # HTML H2
            r'<h3>',  # HTML H3
        ]
        
        heading_count = 0
        for pattern in heading_patterns:
            matches = re.findall(pattern, body, re.MULTILINE)
            heading_count += len(matches)
        
        if heading_count < self.min_headings:
            issues.append(
                f"Insufficient section headings ({heading_count}/{self.min_headings} required)"
            )
        
        details["headings"] = heading_count
        
        # Check 4: FAQ section (for citation-ready answers)
        faq_indicators = [
            r'\b(?:faq|frequently asked|questions? and answers?|q&a)\b',
            r'\b(?:what is|how does|why|when|where)\b',  # Question words
        ]
        
        has_faq_section = any(
            re.search(pattern, body_lower, re.IGNORECASE)
            for pattern in faq_indicators
        )
        
        # Count question-answer pairs
        question_markers = re.findall(r'\?', body)
        qa_pairs = len(question_markers)
        
        if not has_faq_section or qa_pairs < 2:
            issues.append("Missing FAQ section or insufficient Q&A pairs (minimum 2 required)")
        
        details["has_faq_section"] = has_faq_section
        details["qa_pairs"] = qa_pairs
        
        # Check 5: Structured data format (tables, lists, clear sections)
        has_structure = (
            bullet_count > 0
            or heading_count > 0
            or bool(re.search(r'\|.*\|', body))  # Markdown table
            or bool(re.search(r'<table>', body_lower))  # HTML table
        )
        
        if not has_structure:
            issues.append("Content lacks structured formatting (lists, tables, or clear sections)")
        
        details["has_structure"] = has_structure
        
        # Calculate GEO score
        geo_score = (
            (1.0 if has_direct_answer else 0.0) * 0.3
            + (min(1.0, bullet_count / 5.0)) * 0.2
            + (min(1.0, heading_count / 5.0)) * 0.2
            + (1.0 if has_faq_section and qa_pairs >= 2 else 0.0) * 0.2
            + (1.0 if has_structure else 0.0) * 0.1
        )
        
        details["geo_score"] = geo_score
        
        if issues:
            return {
                "passed": False,
                "reason": "; ".join(issues),
                "details": details,
            }
        
        return {
            "passed": True,
            "details": details,
        }
    
    def get_geo_prompt_enhancement(self) -> str:
        """
        Get prompt enhancement for GEO formatting requirements.
        
        Returns:
            String to append to generation prompts
        """
        return """
        
GEO (Generative Engine Optimization) Requirements:
1. Start with a direct answer to the main question in the first 200 characters
2. Use bullet points (- or *) for key information (minimum 3 bullets)
3. Include clear section headings (## for H2, ### for H3, minimum 2 headings)
4. Add an FAQ section with at least 2 question-answer pairs
5. Use structured formatting (lists, tables) for easy AI citation
6. Make content easily scrapable by AI systems (clear, concise, direct)
"""

