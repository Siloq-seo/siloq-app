"""Cannibalization prevention through vector similarity detection"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pgvector.sqlalchemy import Vector
import numpy as np

from app.db.models import Page, CannibalizationCheck, ContentStatus
from app.core.config import settings
from app.types import CannibalizationResult, SimilarContentItem


class CannibalizationDetector:
    """Detects content cannibalization using vector embeddings"""

    def __init__(self, threshold: float = None):
        self.threshold = threshold or settings.cannibalization_threshold

    async def check_cannibalization(
        self,
        db: AsyncSession,
        content_id: UUID,
        embedding: List[float],
        site_id: UUID,
        exclude_content_ids: Optional[List[UUID]] = None,
    ) -> CannibalizationResult:
        """
        Check if new content would cannibalize existing content
        
        Returns:
            {
                "is_cannibalized": bool,
                "similar_content": List[dict],
                "max_similarity": float
            }
        """
        exclude_content_ids = exclude_content_ids or []
        if content_id not in exclude_content_ids:
            exclude_content_ids.append(content_id)

        # Query for similar content using pgvector cosine similarity
        # Using 1 - cosine_distance to get similarity score
        query = select(
            Page.id,
            Page.title,
            Page.path,
            (1 - Page.embedding.cosine_distance(embedding)).label("similarity"),
        ).where(
            and_(
                Page.site_id == site_id,
                Page.embedding.isnot(None),
                Page.id.notin_(exclude_content_ids),
                Page.status.in_([ContentStatus.PUBLISHED, ContentStatus.APPROVED]),
            )
        ).order_by(
            Page.embedding.cosine_distance(embedding)
        ).limit(10)

        result = await db.execute(query)
        similar_content = []

        max_similarity = 0.0
        for row in result:
            similarity = float(row.similarity)
            max_similarity = max(max_similarity, similarity)

            if similarity >= self.threshold:
                similar_content.append(
                    {
                        "id": str(row.id),
                        "title": row.title,
                        "path": row.path,
                        "similarity": similarity,
                    }
                )

        is_cannibalized = max_similarity >= self.threshold

        # Record the check
        if similar_content:
            for item in similar_content:
                check = CannibalizationCheck(
                    page_id=content_id,
                    compared_with_id=UUID(item["id"]),
                    similarity_score=item["similarity"],
                    threshold_exceeded=True,
                )
                db.add(check)

        return {
            "is_cannibalized": is_cannibalized,
            "similar_content": similar_content,
            "max_similarity": max_similarity,
            "threshold": self.threshold,
        }

    async def validate_no_cannibalization(
        self,
        db: AsyncSession,
        content_id: UUID,
        embedding: List[float],
        site_id: UUID,
    ) -> bool:
        """Validate that content does not cannibalize existing content"""
        result = await self.check_cannibalization(
            db, content_id, embedding, site_id
        )
        return not result["is_cannibalized"]

