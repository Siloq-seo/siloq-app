"""Near-duplicate intent detection with multiple similarity thresholds."""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.vector_similarity import VectorSimilarity, SimilarContent
from app.decision.error_codes import ErrorCode, ErrorCodeDictionary


class SimilarityLevel(str, Enum):
    """Similarity level classifications."""
    
    EXACT_DUPLICATE = "exact_duplicate"  # >= 0.95
    NEAR_DUPLICATE_INTENT = "near_duplicate_intent"  # >= 0.85
    SIMILAR_INTENT = "similar_intent"  # >= 0.70
    DISTINCT_INTENT = "distinct_intent"  # < 0.70


@dataclass
class DetectionResult:
    """Result of near-duplicate detection."""
    
    is_duplicate: bool
    similarity_level: SimilarityLevel
    max_similarity: float
    similar_content: List[SimilarContent]
    error_code: Optional[ErrorCode] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "is_duplicate": self.is_duplicate,
            "similarity_level": self.similarity_level.value,
            "max_similarity": self.max_similarity,
            "similar_content": [sc.to_dict() for sc in self.similar_content],
            "error_code": self.error_code.code if self.error_code else None,
        }


class NearDuplicateDetector:
    """
    Detects near-duplicate content by intent using vector similarity.
    
    Uses multiple thresholds to classify similarity levels and
    blocks content that would create intent collisions.
    """
    
    # Similarity thresholds
    EXACT_DUPLICATE_THRESHOLD = 0.95
    NEAR_DUPLICATE_THRESHOLD = 0.85
    SIMILAR_INTENT_THRESHOLD = 0.70
    
    def __init__(self, threshold: float = None):
        """
        Initialize near-duplicate detector.
        
        Args:
            threshold: Blocking threshold (default: 0.85)
        """
        self.vector_similarity = VectorSimilarity(threshold=threshold)
        self.blocking_threshold = threshold or self.NEAR_DUPLICATE_THRESHOLD
    
    def _classify_similarity_level(self, similarity: float) -> SimilarityLevel:
        """
        Classify similarity score into level.
        
        Args:
            similarity: Similarity score (0.0 to 1.0)
            
        Returns:
            SimilarityLevel enum value
        """
        if similarity >= self.EXACT_DUPLICATE_THRESHOLD:
            return SimilarityLevel.EXACT_DUPLICATE
        elif similarity >= self.NEAR_DUPLICATE_THRESHOLD:
            return SimilarityLevel.NEAR_DUPLICATE_INTENT
        elif similarity >= self.SIMILAR_INTENT_THRESHOLD:
            return SimilarityLevel.SIMILAR_INTENT
        else:
            return SimilarityLevel.DISTINCT_INTENT
    
    async def detect_near_duplicates(
        self,
        db: AsyncSession,
        page_id: UUID,
        embedding: List[float],
        site_id: UUID,
    ) -> DetectionResult:
        """
        Detect near-duplicate content by intent.
        
        Args:
            db: Database session
            page_id: Page identifier
            embedding: Page embedding vector
            site_id: Site identifier
            
        Returns:
            DetectionResult with similarity classification
        """
        # Find similar content
        similar_content = await self.vector_similarity.find_similar_content(
            db,
            embedding,
            site_id,
            threshold=self.SIMILAR_INTENT_THRESHOLD,
            exclude_page_ids=[page_id],
        )
        
        if not similar_content:
            return DetectionResult(
                is_duplicate=False,
                similarity_level=SimilarityLevel.DISTINCT_INTENT,
                max_similarity=0.0,
                similar_content=[],
            )
        
        # Get maximum similarity
        max_similarity = max(sc.similarity for sc in similar_content)
        similarity_level = self._classify_similarity_level(max_similarity)
        
        # Determine if it's a duplicate (blocking)
        is_duplicate = max_similarity >= self.blocking_threshold
        
        # Get error code if duplicate
        error_code = None
        if is_duplicate:
            if similarity_level == SimilarityLevel.EXACT_DUPLICATE:
                error_code = ErrorCodeDictionary.PREFLIGHT_007  # Use existing error code
            else:
                # Use NEAR_DUPLICATE_INTENT error code
                error_code = ErrorCodeDictionary.NEAR_DUPLICATE_INTENT
        
        return DetectionResult(
            is_duplicate=is_duplicate,
            similarity_level=similarity_level,
            max_similarity=max_similarity,
            similar_content=similar_content,
            error_code=error_code,
        )
    
    async def check_intent_collision(
        self,
        db: AsyncSession,
        embedding: List[float],
        site_id: UUID,
        exclude_page_id: Optional[UUID] = None,
    ) -> Tuple[bool, float, Optional[SimilarContent]]:
        """
        Check if content would create an intent collision.
        
        Args:
            db: Database session
            embedding: Embedding vector to check
            site_id: Site identifier
            exclude_page_id: Page ID to exclude from check
            
        Returns:
            Tuple of (has_collision, max_similarity, most_similar_content)
        """
        exclude_ids = [exclude_page_id] if exclude_page_id else []
        
        max_similarity, most_similar = await self.vector_similarity.get_max_similarity(
            db, embedding, site_id, exclude_page_ids=exclude_ids
        )
        
        has_collision = max_similarity >= self.blocking_threshold
        
        return has_collision, max_similarity, most_similar

