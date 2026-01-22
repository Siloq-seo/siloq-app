"""Deterministic vector similarity scoring for cannibalization detection."""
from typing import List, Optional, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from pgvector.sqlalchemy import Vector

from app.db.models import Page
from app.core.config import settings


class SimilarContent:
    """Represents similar content with similarity score."""
    
    def __init__(
        self,
        page_id: UUID,
        title: str,
        slug: str,
        similarity: float,
        path: Optional[str] = None,
    ):
        self.page_id = page_id
        self.title = title
        self.slug = slug
        self.similarity = similarity
        self.path = path
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.page_id),
            "title": self.title,
            "slug": self.slug,
            "similarity": self.similarity,
            "path": self.path,
        }


class VectorSimilarity:
    """
    Deterministic similarity scoring using cosine similarity.
    
    Provides consistent, reproducible similarity calculations
    for cannibalization detection.
    """
    
    def __init__(self, threshold: float = None):
        """
        Initialize vector similarity calculator.
        
        Args:
            threshold: Similarity threshold (default: 0.85)
        """
        self.threshold = threshold or settings.cannibalization_threshold
    
    @staticmethod
    def calculate_similarity(
        embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Deterministic: same inputs always produce same output.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between 0.0 and 1.0
            
        Raises:
            ValueError: If embeddings have different dimensions
        """
        if len(embedding1) != len(embedding2):
            raise ValueError(
                f"Embeddings must have same dimensions: "
                f"{len(embedding1)} vs {len(embedding2)}"
            )
        
        # Convert to numpy arrays for efficient computation
        vec1 = np.array(embedding1, dtype=np.float32)
        vec2 = np.array(embedding2, dtype=np.float32)
        
        # Calculate cosine similarity: dot product / (norm1 * norm2)
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # Ensure result is between 0 and 1
        return float(np.clip(similarity, 0.0, 1.0))
    
    async def find_similar_content(
        self,
        db: AsyncSession,
        embedding: List[float],
        site_id: UUID,
        threshold: Optional[float] = None,
        exclude_page_ids: Optional[List[UUID]] = None,
        limit: int = 10,
    ) -> List[SimilarContent]:
        """
        Find similar content using pgvector cosine similarity.
        
        Args:
            db: Database session
            embedding: Embedding vector to compare
            site_id: Site identifier
            threshold: Similarity threshold (default: self.threshold)
            exclude_page_ids: Page IDs to exclude from results
            limit: Maximum number of results
            
        Returns:
            List of SimilarContent objects sorted by similarity (descending)
        """
        threshold = threshold or self.threshold
        exclude_page_ids = exclude_page_ids or []
        
        # Build query using pgvector cosine distance
        # Similarity = 1 - cosine_distance
        query = select(
            Page.id,
            Page.title,
            Page.path,
            (1 - Page.embedding.cosine_distance(embedding)).label("similarity"),
        ).where(
            and_(
                Page.site_id == site_id,
                Page.embedding.isnot(None),
                Page.id.notin_(exclude_page_ids) if exclude_page_ids else True,
                Page.status.in_(["published", "approved"]),
            )
        ).order_by(
            Page.embedding.cosine_distance(embedding)
        ).limit(limit)
        
        result = await db.execute(query)
        
        similar_content = []
        for row in result:
            similarity = float(row.similarity)
            
            # Only include if above threshold
            if similarity >= threshold:
                similar_content.append(
                    SimilarContent(
                        page_id=row.id,
                        title=row.title,
                        slug=row.path.lstrip("/") if row.path else "",
                        similarity=similarity,
                        path=row.path,
                    )
                )
        
        return similar_content
    
    async def get_max_similarity(
        self,
        db: AsyncSession,
        embedding: List[float],
        site_id: UUID,
        exclude_page_ids: Optional[List[UUID]] = None,
    ) -> Tuple[float, Optional[SimilarContent]]:
        """
        Get maximum similarity score and most similar content.
        
        Args:
            db: Database session
            embedding: Embedding vector to compare
            site_id: Site identifier
            exclude_page_ids: Page IDs to exclude
            
        Returns:
            Tuple of (max_similarity, most_similar_content)
        """
        similar_content = await self.find_similar_content(
            db, embedding, site_id, threshold=0.0, exclude_page_ids=exclude_page_ids, limit=1
        )
        
        if similar_content:
            return similar_content[0].similarity, similar_content[0]
        
        return 0.0, None

