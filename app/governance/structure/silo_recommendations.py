"""Silo recommendations based on content clusters."""
import re
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.db.models import Page, Cluster, ClusterPage, Silo, PageSilo
from app.governance.structure.clusters import ClusterManager
from app.governance.structure.reverse_silos import ReverseSiloEnforcer

# Constants
MIN_CLUSTER_PAGES_FOR_SILO = 3
MAX_RECOMMENDED_PAGES = 5
MAX_ASSIGNMENT_PAGES = 10
MAX_SUPPORTING_PAGES = 20
MAX_UNASSIGNED_PAGES = 50
PUBLISHED_STATUSES = ["published", "approved"]


class SiloRecommendationEngine:
    """
    Generates silo recommendations based on content clusters.
    
    Analyzes existing content and clusters to recommend:
    - New silos to create
    - Pages to add to existing silos
    - Supporting page assignments
    """
    
    def __init__(self):
        """Initialize recommendation engine with dependencies."""
        self.cluster_manager = ClusterManager()
        self.silo_enforcer = ReverseSiloEnforcer()
    
    async def generate_recommendations(
        self,
        db: AsyncSession,
        site_id: UUID,
    ) -> Dict:
        """
        Generate silo recommendations for a site.
        
        Analyzes clusters and existing silos to provide actionable
        recommendations for silo structure optimization.
        
        Args:
            db: Database session
            site_id: Site identifier
            
        Returns:
            Dictionary with recommendations including:
            - new_silos: Recommended new silos to create
            - page_assignments: Pages to add to existing silos
            - supporting_pages: Pages that could be supporting pages
            - cluster_analysis: Analysis of all clusters
        """
        recommendations = {
            "new_silos": [],
            "page_assignments": [],
            "supporting_pages": [],
            "cluster_analysis": [],
        }
        
        # Get existing silos and clusters
        existing_silos = await self.silo_enforcer.get_silos_for_site(db, str(site_id))
        existing_silo_ids = {silo.id for silo in existing_silos}
        clusters = await self.cluster_manager.get_clusters_for_site(db, site_id)
        
        # Analyze each cluster
        for cluster in clusters:
            cluster_pages = await self.cluster_manager.get_cluster_pages(
                db, cluster.cluster_id
            )
            
            cluster_silo = None
            if len(cluster_pages) >= MIN_CLUSTER_PAGES_FOR_SILO:
                cluster_silo = await self._find_cluster_silo(
                    db, cluster.cluster_id, existing_silo_ids
                )
                
                if not cluster_silo:
                    # Recommend new silo for this cluster
                    recommendations["new_silos"].append(
                        self._create_new_silo_recommendation(cluster, cluster_pages)
                    )
                else:
                    # Recommend page assignments to existing silo
                    assignment = await self._create_page_assignment_recommendation(
                        db, cluster, cluster_pages, cluster_silo, existing_silos
                    )
                    if assignment:
                        recommendations["page_assignments"].append(assignment)
            
            # Add cluster analysis
            recommendations["cluster_analysis"].append(
                self._create_cluster_analysis(cluster, cluster_pages, cluster_silo)
            )
        
        # Find supporting pages
        supporting_pages = await self._find_supporting_pages(db, site_id)
        recommendations["supporting_pages"] = supporting_pages[:MAX_SUPPORTING_PAGES]
        
        return recommendations
    
    def _create_new_silo_recommendation(
        self,
        cluster,
        cluster_pages: List[Dict],
    ) -> Dict:
        """Create recommendation for a new silo from a cluster."""
        return {
            "cluster_id": str(cluster.cluster_id),
            "cluster_name": cluster.name,
            "recommended_silo_name": cluster.name,
            "recommended_slug": self._slugify(cluster.name),
            "page_count": len(cluster_pages),
            "pages": cluster_pages[:MAX_RECOMMENDED_PAGES],
        }
    
    async def _create_page_assignment_recommendation(
        self,
        db: AsyncSession,
        cluster,
        cluster_pages: List[Dict],
        cluster_silo: UUID,
        existing_silos: List,
    ) -> Optional[Dict]:
        """Create recommendation for assigning pages to existing silo."""
        unassigned = [
            p
            for p in cluster_pages
            if not await self._is_page_in_silo(db, UUID(p["page_id"]), cluster_silo)
        ]
        
        if not unassigned:
            return None
        
        silo_name = next(s.name for s in existing_silos if s.id == cluster_silo)
        
        return {
            "silo_id": str(cluster_silo),
            "silo_name": silo_name,
            "pages": unassigned[:MAX_ASSIGNMENT_PAGES],
        }
    
    def _create_cluster_analysis(
        self,
        cluster,
        cluster_pages: List[Dict],
        cluster_silo: Optional[UUID],
    ) -> Dict:
        """Create analysis entry for a cluster."""
        return {
            "cluster_id": str(cluster.cluster_id),
            "cluster_name": cluster.name,
            "page_count": len(cluster_pages),
            "has_silo": cluster_silo is not None,
        }
    
    async def _find_cluster_silo(
        self,
        db: AsyncSession,
        cluster_id: UUID,
        existing_silo_ids: set,
    ) -> Optional[UUID]:
        """
        Find if cluster maps to an existing silo.
        
        Uses name matching to identify potential silo matches.
        
        Args:
            db: Database session
            cluster_id: Cluster identifier
            existing_silo_ids: Set of existing silo IDs
            
        Returns:
            Matching silo ID if found, None otherwise
        """
        cluster = await db.get(Cluster, cluster_id)
        if not cluster:
            return None
        
        query = select(Silo).where(
            and_(
                Silo.site_id == cluster.site_id,
                Silo.name.ilike(f"%{cluster.name}%"),
            )
        )
        result = await db.execute(query)
        silo = result.scalar_one_or_none()
        
        return silo.id if silo and silo.id in existing_silo_ids else None
    
    async def _is_page_in_silo(
        self,
        db: AsyncSession,
        page_id: UUID,
        silo_id: UUID,
    ) -> bool:
        """Check if a page is already assigned to a silo."""
        query = select(PageSilo).where(
            and_(
                PageSilo.page_id == page_id,
                PageSilo.silo_id == silo_id,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def _find_supporting_pages(
        self,
        db: AsyncSession,
        site_id: UUID,
    ) -> List[Dict]:
        """
        Find pages that could be supporting pages.
        
        Identifies published pages not currently assigned to any silo.
        
        Args:
            db: Database session
            site_id: Site identifier
            
        Returns:
            List of page dictionaries with metadata
        """
        query = (
            select(Page)
            .where(
                and_(
                    Page.site_id == site_id,
                    Page.status.in_(PUBLISHED_STATUSES),
                    ~Page.id.in_(select(PageSilo.page_id).distinct()),
                )
            )
            .limit(MAX_UNASSIGNED_PAGES)
        )
        
        result = await db.execute(query)
        pages = result.scalars().all()
        
        return [
            {
                "page_id": str(page.id),
                "title": page.title,
                "path": page.path,
                "authority_score": page.authority_score or 0.0,
            }
            for page in pages
        ]
    
    @staticmethod
    def _slugify(text: str) -> str:
        """
        Convert text to URL-friendly slug.
        
        Args:
            text: Text to convert
            
        Returns:
            URL-friendly slug string
        """
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text
