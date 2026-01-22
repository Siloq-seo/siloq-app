"""Content clusters for grouping related pages."""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.models import Page, Cluster, ClusterPage


class ClusterRole:
    """Roles for pages within clusters."""
    
    MEMBER = "member"
    ANCHOR = "anchor"
    HUB = "hub"
    
    @classmethod
    def is_valid(cls, role: str) -> bool:
        """Check if a role is valid."""
        return role in (cls.MEMBER, cls.ANCHOR, cls.HUB)


class Cluster:
    """Represents a content cluster."""
    
    def __init__(
        self,
        cluster_id: UUID,
        site_id: UUID,
        name: str,
        description: Optional[str] = None,
    ):
        """
        Initialize a cluster.
        
        Args:
            cluster_id: Unique cluster identifier
            site_id: Site this cluster belongs to
            name: Cluster name
            description: Optional cluster description
        """
        self.cluster_id = cluster_id
        self.site_id = site_id
        self.name = name
        self.description = description
    
    def to_dict(self) -> dict:
        """Convert cluster to dictionary for API responses."""
        return {
            "id": str(self.cluster_id),
            "site_id": str(self.site_id),
            "name": self.name,
            "description": self.description,
        }


class ClusterManager:
    """
    Manages content clusters for grouping related pages.
    
    Clusters help organize content into logical groups that can be
    used for silo recommendations and structure optimization.
    """
    
    async def create_cluster(
        self,
        db: AsyncSession,
        site_id: UUID,
        name: str,
        description: Optional[str] = None,
    ) -> Cluster:
        """
        Create a new content cluster.
        
        Args:
            db: Database session
            site_id: Site identifier
            name: Cluster name (must be unique per site)
            description: Optional cluster description
            
        Returns:
            Created Cluster object
            
        Raises:
            IntegrityError: If cluster name already exists for site
        """
        cluster = Cluster(
            site_id=site_id,
            name=name,
            description=description,
        )
        
        db.add(cluster)
        await db.commit()
        await db.refresh(cluster)
        
        return Cluster(
            cluster_id=cluster.id,
            site_id=cluster.site_id,
            name=cluster.name,
            description=cluster.description,
        )
    
    async def add_page_to_cluster(
        self,
        db: AsyncSession,
        cluster_id: UUID,
        page_id: UUID,
        role: str = ClusterRole.MEMBER,
    ) -> bool:
        """
        Add a page to a cluster with specified role.
        
        If page is already in cluster, updates the role.
        
        Args:
            db: Database session
            cluster_id: Cluster identifier
            page_id: Page identifier
            role: Page role in cluster (member, anchor, hub)
            
        Returns:
            True if successful
        """
        if not ClusterRole.is_valid(role):
            role = ClusterRole.MEMBER
        
        # Check if relationship already exists
        existing = await self._get_cluster_page(db, cluster_id, page_id)
        
        if existing:
            existing.role = role
        else:
            cluster_page = ClusterPage(
                cluster_id=cluster_id,
                page_id=page_id,
                role=role,
            )
            db.add(cluster_page)
        
        await db.commit()
        return True
    
    async def _get_cluster_page(
        self,
        db: AsyncSession,
        cluster_id: UUID,
        page_id: UUID,
    ) -> Optional[ClusterPage]:
        """Get existing cluster-page relationship if it exists."""
        query = select(ClusterPage).where(
            and_(
                ClusterPage.cluster_id == cluster_id,
                ClusterPage.page_id == page_id,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_cluster_pages(
        self,
        db: AsyncSession,
        cluster_id: UUID,
    ) -> List[dict]:
        """
        Get all pages in a cluster with their roles.
        
        Args:
            db: Database session
            cluster_id: Cluster identifier
            
        Returns:
            List of page dictionaries with role information
        """
        query = (
            select(ClusterPage, Page)
            .join(Page, ClusterPage.page_id == Page.id)
            .where(ClusterPage.cluster_id == cluster_id)
        )
        
        result = await db.execute(query)
        
        return [
            {
                "page_id": str(page.id),
                "title": page.title,
                "path": page.path,
                "role": cluster_page.role,
            }
            for cluster_page, page in result
        ]
    
    async def get_clusters_for_site(
        self,
        db: AsyncSession,
        site_id: UUID,
    ) -> List[Cluster]:
        """
        Get all clusters for a site.
        
        Args:
            db: Database session
            site_id: Site identifier
            
        Returns:
            List of Cluster objects for the site
        """
        query = select(Cluster).where(Cluster.site_id == site_id)
        result = await db.execute(query)
        clusters = result.scalars().all()
        
        return [
            Cluster(
                cluster_id=cluster.id,
                site_id=cluster.site_id,
                name=cluster.name,
                description=cluster.description,
            )
            for cluster in clusters
        ]
