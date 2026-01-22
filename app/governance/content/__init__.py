"""Content quality and publishing governance"""
from app.governance.content.cannibalization import CannibalizationDetector
from app.governance.content.near_duplicate_detector import NearDuplicateDetector
from app.governance.content.publishing import PublishingSafety

# VectorSimilarityChecker may not exist, import conditionally
try:
    from app.governance.content.vector_similarity import VectorSimilarityChecker
    __all__ = [
        "CannibalizationDetector",
        "NearDuplicateDetector",
        "VectorSimilarityChecker",
        "PublishingSafety",
    ]
except ImportError:
    __all__ = [
        "CannibalizationDetector",
        "NearDuplicateDetector",
        "PublishingSafety",
    ]
