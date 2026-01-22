"""
Future SEO: Agent-Friendly Interface (AFI)

AI agents will soon browse, compare, and transact on behalf of humans.
This module provides a hidden, structured layer designed specifically for
AI Agents to "read" product specs and service values instantly, without
having to parse HTML.
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.models import Page, Site


class AgentFriendlyInterface:
    """
    Generates structured data for AI agents.
    
    This creates a machine-readable layer that AI agents can consume
    without parsing HTML or natural language.
    """
    
    def __init__(self):
        self.afi_version = "1.0"
        self.supported_agent_types = [
            "shopping",
            "comparison",
            "research",
            "transaction",
            "general",
        ]
    
    async def generate_afi_data(
        self,
        db: AsyncSession,
        page: Page,
        agent_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Generate Agent-Friendly Interface data for a page.
        
        Args:
            db: Database session
            page: Page to generate AFI data for
            agent_type: Type of agent (shopping, comparison, research, etc.)
            
        Returns:
            Structured AFI data
        """
        # Base AFI structure
        afi_data = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "afi_version": self.afi_version,
            "agent_type": agent_type,
            "page_id": str(page.id),
            "url": page.path,
            "title": page.title,
            "summary": self._extract_summary(page.body),
            "entities": self._extract_entities(page.body),
            "structured_data": {},
        }
        
        # Agent-specific data
        if agent_type == "shopping":
            afi_data["structured_data"] = self._generate_shopping_data(page)
        elif agent_type == "comparison":
            afi_data["structured_data"] = self._generate_comparison_data(page)
        elif agent_type == "research":
            afi_data["structured_data"] = self._generate_research_data(page)
        
        return afi_data
    
    def _extract_summary(self, body: Optional[str]) -> str:
        """Extract summary from body."""
        if not body:
            return ""
        # Extract first paragraph or first 200 characters
        first_para = body.split('\n\n')[0] if '\n\n' in body else body
        return first_para[:200] + "..." if len(first_para) > 200 else first_para
    
    def _extract_entities(self, body: Optional[str]) -> List[str]:
        """Extract entities from body."""
        # TODO: Implement entity extraction
        # This would use NLP to identify entities
        return []
    
    def _generate_shopping_data(self, page: Page) -> Dict[str, Any]:
        """Generate shopping-specific structured data."""
        return {
            "product_specs": {},
            "pricing": {},
            "availability": {},
            "reviews": {},
        }
    
    def _generate_comparison_data(self, page: Page) -> Dict[str, Any]:
        """Generate comparison-specific structured data."""
        return {
            "comparison_points": [],
            "pros": [],
            "cons": [],
            "alternatives": [],
        }
    
    def _generate_research_data(self, page: Page) -> Dict[str, Any]:
        """Generate research-specific structured data."""
        return {
            "key_findings": [],
            "data_points": [],
            "sources": page.source_urls or [],
            "methodology": {},
        }
    
    async def get_afi_endpoint_url(
        self,
        page: Page,
        agent_type: str = "general",
    ) -> str:
        """
        Get the AFI endpoint URL for a page.
        
        Args:
            page: Page
            agent_type: Type of agent
            
        Returns:
            URL to AFI data endpoint
        """
        # This would be a hidden endpoint like:
        # /api/afi/{page_id}?agent_type={agent_type}
        return f"/api/afi/{page.id}?agent_type={agent_type}"

