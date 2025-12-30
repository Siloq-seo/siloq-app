"""Hybrid JSON-LD schema generation (backend-driven, not AI-generated)"""
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Page, Site, Silo
from app.governance.page_helpers import get_page_silo_id, get_page_slug


class JSONLDGenerator:
    """Generates structured JSON-LD schemas using backend logic"""

    def __init__(self):
        pass

    async def generate_schema(
        self, db: AsyncSession, page: Page
    ) -> Dict[str, Any]:
        """
        Generate JSON-LD schema for content
        
        This is backend-driven, not AI-generated, ensuring structure and consistency
        """
        # Get site and silo information
        site = await db.get(Site, page.site_id)
        silo = None
        silo_id = get_page_silo_id(page)
        if silo_id:
            silo = await db.get(Silo, silo_id)

        slug = get_page_slug(page)

        # Base Article schema
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": page.title,
            "description": self._extract_description(page.body),
            "datePublished": page.created_at.isoformat() if page.created_at else None,
            "dateModified": page.updated_at.isoformat() if page.updated_at else None,
            "author": {
                "@type": "Organization",
                "name": site.name if site else "Unknown",
            },
            "publisher": {
                "@type": "Organization",
                "name": site.name if site else "Unknown",
                "url": f"https://{site.domain}" if site and site.domain else None,
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": f"https://{site.domain}{page.path}" if site and site.domain else None,
            },
        }

        # Add breadcrumb structure (Reverse Silos)
        if silo and site:
            breadcrumb = {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": site.name,
                        "item": f"https://{site.domain}",
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": silo.name,
                        "item": f"https://{site.domain}/{silo.slug}",
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": page.title,
                        "item": f"https://{site.domain}{page.path}",
                    },
                ],
            }
            schema["breadcrumb"] = breadcrumb

        # Add organization schema for site
        if site:
            organization_schema = {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": site.name,
                "url": f"https://{site.domain}",
            }
            schema["publisher"] = organization_schema

        # Add authority/source citations if available
        if page.source_urls:
            citations = []
            for idx, url in enumerate(page.source_urls[:5], 1):  # Limit to 5 sources
                citations.append({
                    "@type": "WebPage",
                    "position": idx,
                    "url": url,
                })
            if citations:
                schema["citation"] = citations

        # Add content rating if authority score is high
        if page.authority_score > 0.7:
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": round(page.authority_score * 5, 1),  # Convert to 5-star scale
                "bestRating": 5,
                "worstRating": 1,
            }

        return schema

    def _extract_description(self, body: str, max_length: int = 160) -> str:
        """Extract description from content body"""
        if not body:
            return ""
        
        # Remove HTML tags if present
        import re
        text = re.sub(r'<[^>]+>', '', body)
        
        # Get first sentence or first N characters
        sentences = text.split('.')
        if sentences and len(sentences[0]) <= max_length:
            return sentences[0].strip() + '.'
        
        # Truncate to max_length
        return text[:max_length].strip() + '...'

    async def generate_website_schema(
        self, db: AsyncSession, site: Site
    ) -> Dict[str, Any]:
        """Generate JSON-LD schema for the entire website"""
        schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": site.name,
            "url": f"https://{site.domain}",
        }

        # Add search action if applicable
        schema["potentialAction"] = {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"https://{site.domain}/search?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        }

        return schema

    async def generate_silo_schema(
        self, db: AsyncSession, silo: Silo, site: Site
    ) -> Dict[str, Any]:
        """Generate JSON-LD schema for a silo"""
        schema = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": silo.name,
            "url": f"https://{site.domain}/{silo.slug}",
            "isPartOf": {
                "@type": "WebSite",
                "name": site.name,
                "url": f"https://{site.domain}",
            },
        }

        return schema

