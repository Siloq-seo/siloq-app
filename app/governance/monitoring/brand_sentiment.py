"""
2026 Governance Enhancement: Brand Sentiment Gate (V3 Foundation)

Siloq V3 (The Strategist): Brand Sentiment Monitoring

Siloq currently functions as an "Authority Island"—it governs everything *on* the
site but ignores the world *outside* it. Google's "E-E-A-T" is increasingly
calculated by looking at brand mentions on Reddit, Quora, and high-authority forums.

This module provides a foundation for off-page sentiment monitoring:
- Listener to track how the brand is discussed externally
- Sentiment analysis from external sources (Reddit, Quora, forums)
- Suggests "Restoration" content to address common complaints or gaps
- Turns external "weaknesses" into internal "silo strengths"
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Page, SystemEvent
from app.core.config import settings


class SentimentSource(str, Enum):
    """Sources for sentiment monitoring"""
    REDDIT = "reddit"
    QUORA = "quora"
    FORUM = "forum"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    REVIEW_SITE = "review_site"
    NEWS = "news"


class SentimentPolarity(str, Enum):
    """Sentiment polarity"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class BrandSentimentMonitor:
    """
    Monitors brand sentiment from external sources (V3 Foundation).
    
    This is a foundation module for Siloq V3 (The Strategist). It provides
    the structure for off-page sentiment monitoring but requires external
    data sources to be fully functional.
    
    Features:
    - Track brand mentions across external platforms
    - Analyze sentiment (positive/negative/neutral)
    - Identify common complaints or gaps
    - Suggest restoration content to address weaknesses
    """
    
    def __init__(self):
        # Sentiment monitoring configuration
        self.sentiment_sources = [
            SentimentSource.REDDIT,
            SentimentSource.QUORA,
            SentimentSource.FORUM,
        ]
        self.sentiment_threshold_days = 30  # Monitor mentions from last N days
    
    async def monitor_brand_sentiment(
        self,
        db: AsyncSession,
        brand_name: str,
        site_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Monitor brand sentiment across external sources.
        
        This is a foundation method. In a full V3 implementation, this would:
        1. Query external APIs (Reddit API, Quora API, etc.)
        2. Analyze sentiment using NLP models
        3. Aggregate results by topic/theme
        4. Identify patterns and gaps
        
        Args:
            db: Database session
            brand_name: Brand name to monitor
            site_id: Optional site ID for context
            
        Returns:
            Sentiment monitoring result
        """
        sentiment_data = {
            "brand_name": brand_name,
            "monitoring_period_days": self.sentiment_threshold_days,
            "sources": [],
            "overall_sentiment": None,
            "topics": [],
            "recommendations": [],
        }
        
        # For each source, collect sentiment data
        for source in self.sentiment_sources:
            source_sentiment = await self._monitor_source_sentiment(
                db,
                brand_name,
                source,
            )
            sentiment_data["sources"].append(source_sentiment)
        
        # Aggregate overall sentiment
        sentiment_data["overall_sentiment"] = self._aggregate_sentiment(
            sentiment_data["sources"]
        )
        
        # Identify topics/themes
        sentiment_data["topics"] = await self._identify_topics(
            db,
            sentiment_data["sources"],
        )
        
        # Generate recommendations for restoration content
        sentiment_data["recommendations"] = await self._generate_restoration_recommendations(
            db,
            sentiment_data["topics"],
            site_id,
        )
        
        # Log sentiment monitoring
        audit = SystemEvent(
            event_type="brand_sentiment_monitored",
            entity_type="site" if site_id else "system",
            entity_id=site_id,
            payload={
                "brand_name": brand_name,
                "overall_sentiment": sentiment_data["overall_sentiment"],
                "topics_count": len(sentiment_data["topics"]),
                "recommendations_count": len(sentiment_data["recommendations"]),
            },
        )
        db.add(audit)
        
        return sentiment_data
    
    async def _monitor_source_sentiment(
        self,
        db: AsyncSession,
        brand_name: str,
        source: SentimentSource,
    ) -> Dict[str, Any]:
        """
        Monitor sentiment from a specific source.
        
        In a full V3 implementation, this would:
        - Query source API (Reddit API, Quora API, etc.)
        - Fetch recent mentions (last N days)
        - Analyze sentiment for each mention
        - Aggregate by topic/theme
        
        For now, returns mock structure.
        """
        # TODO: Implement actual API integration
        # Example for Reddit:
        # reddit_api = RedditAPI()
        # mentions = await reddit_api.search(brand_name, limit=100, time_filter='month')
        # sentiments = await analyze_sentiment(mentions)
        
        return {
            "source": source.value,
            "mention_count": 0,  # Would be populated from API
            "sentiment_distribution": {
                "positive": 0,
                "negative": 0,
                "neutral": 0,
            },
            "top_mentions": [],  # List of {text, sentiment, url, date}
            "topics": [],
        }
    
    def _aggregate_sentiment(
        self,
        source_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Aggregate sentiment across all sources."""
        total_positive = 0
        total_negative = 0
        total_neutral = 0
        total_mentions = 0
        
        for source_result in source_results:
            dist = source_result.get("sentiment_distribution", {})
            total_positive += dist.get("positive", 0)
            total_negative += dist.get("negative", 0)
            total_neutral += dist.get("neutral", 0)
            total_mentions += source_result.get("mention_count", 0)
        
        if total_mentions == 0:
            return {
                "polarity": SentimentPolarity.NEUTRAL.value,
                "score": 0.0,
                "distribution": {
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0,
                },
            }
        
        # Calculate sentiment score (-1 to 1)
        sentiment_score = (total_positive - total_negative) / total_mentions
        
        # Determine polarity
        if sentiment_score > 0.1:
            polarity = SentimentPolarity.POSITIVE.value
        elif sentiment_score < -0.1:
            polarity = SentimentPolarity.NEGATIVE.value
        else:
            polarity = SentimentPolarity.NEUTRAL.value
        
        return {
            "polarity": polarity,
            "score": sentiment_score,
            "distribution": {
                "positive": total_positive,
                "negative": total_negative,
                "neutral": total_neutral,
            },
            "total_mentions": total_mentions,
        }
    
    async def _identify_topics(
        self,
        db: AsyncSession,
        source_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Identify topics/themes from sentiment data.
        
        Groups mentions by topic and calculates sentiment per topic.
        """
        topics = []
        
        # In a full implementation, would use topic modeling (LDA, BERTopic, etc.)
        # to identify recurring themes from mentions
        
        # Aggregate topics from all sources
        topic_aggregation = {}
        for source_result in source_results:
            source_topics = source_result.get("topics", [])
            for topic in source_topics:
                topic_name = topic.get("name", "")
                if topic_name:
                    if topic_name not in topic_aggregation:
                        topic_aggregation[topic_name] = {
                            "name": topic_name,
                            "mention_count": 0,
                            "positive_count": 0,
                            "negative_count": 0,
                            "neutral_count": 0,
                        }
                    topic_aggregation[topic_name]["mention_count"] += topic.get("count", 0)
                    topic_aggregation[topic_name]["positive_count"] += topic.get("positive", 0)
                    topic_aggregation[topic_name]["negative_count"] += topic.get("negative", 0)
                    topic_aggregation[topic_name]["neutral_count"] += topic.get("neutral", 0)
        
        # Convert to list and calculate sentiment per topic
        for topic_name, topic_data in topic_aggregation.items():
            total = topic_data["mention_count"]
            if total > 0:
                sentiment_score = (
                    topic_data["positive_count"] - topic_data["negative_count"]
                ) / total
                
                topics.append({
                    "name": topic_name,
                    "mention_count": total,
                    "sentiment_score": sentiment_score,
                    "sentiment_polarity": (
                        SentimentPolarity.POSITIVE.value if sentiment_score > 0.1
                        else SentimentPolarity.NEGATIVE.value if sentiment_score < -0.1
                        else SentimentPolarity.NEUTRAL.value
                    ),
                    "positive_count": topic_data["positive_count"],
                    "negative_count": topic_data["negative_count"],
                    "neutral_count": topic_data["neutral_count"],
                })
        
        # Sort by mention count (most mentioned first)
        topics.sort(key=lambda x: x["mention_count"], reverse=True)
        
        return topics
    
    async def _generate_restoration_recommendations(
        self,
        db: AsyncSession,
        topics: List[Dict[str, Any]],
        site_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations for restoration content.
        
        Identifies negative topics and suggests content to address them,
        turning external "weaknesses" into internal "silo strengths."
        """
        recommendations = []
        
        # Focus on negative topics (opportunities for restoration content)
        negative_topics = [
            topic for topic in topics
            if topic.get("sentiment_polarity") == SentimentPolarity.NEGATIVE.value
        ]
        
        for topic in negative_topics[:10]:  # Top 10 negative topics
            recommendation = {
                "topic": topic["name"],
                "reason": f"Negative sentiment detected ({topic['negative_count']} negative mentions)",
                "recommendation_type": "restoration_content",
                "suggested_action": (
                    f"Create content addressing '{topic['name']}' to counter negative sentiment. "
                    "This turns an external weakness into an internal silo strength."
                ),
                "priority": "high" if topic["mention_count"] > 5 else "medium",
                "site_id": site_id,
            }
            recommendations.append(recommendation)
        
        # Also suggest content for topics with high mention volume but neutral sentiment
        # (opportunities to establish authority)
        high_volume_topics = [
            topic for topic in topics
            if topic.get("mention_count", 0) > 10
            and topic.get("sentiment_polarity") == SentimentPolarity.NEUTRAL.value
        ]
        
        for topic in high_volume_topics[:5]:  # Top 5 high-volume neutral topics
            recommendation = {
                "topic": topic["name"],
                "reason": f"High mention volume ({topic['mention_count']} mentions) with neutral sentiment",
                "recommendation_type": "authority_content",
                "suggested_action": (
                    f"Create authoritative content on '{topic['name']}' to establish expertise "
                    "in a frequently discussed area."
                ),
                "priority": "medium",
                "site_id": site_id,
            }
            recommendations.append(recommendation)
        
        return recommendations
    
    async def create_sentiment_gate_check(
        self,
        db: AsyncSession,
        page: Page,
        brand_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a sentiment gate check for a page (V3 Gate).
        
        This would be used as an optional gate in V3 to ensure content
        addresses known negative sentiment topics.
        
        Args:
            db: Database session
            page: Page to check
            brand_name: Optional brand name (if not provided, uses site name)
            
        Returns:
            Gate check result
        """
        # Get brand name from site if not provided
        if not brand_name:
            from app.db.models import Site
            site = await db.get(Site, page.site_id)
            brand_name = site.name if site else None
        
        if not brand_name:
            return {
                "passed": True,
                "reason": "No brand name provided, sentiment gate skipped",
                "details": {},
            }
        
        # Get recent sentiment monitoring results
        sentiment_data = await self.monitor_brand_sentiment(db, brand_name, str(page.site_id))
        
        # Check if page addresses any negative topics
        page_topics = await self._extract_page_topics(page)
        
        # Check if page addresses any recommended restoration topics
        restoration_topics = [
            rec["topic"] for rec in sentiment_data.get("recommendations", [])
            if rec.get("recommendation_type") == "restoration_content"
        ]
        
        addressed_topics = [
            topic for topic in restoration_topics
            if any(
                topic.lower() in page_topic.lower()
                for page_topic in page_topics
            )
        ]
        
        # Gate passes if page addresses at least one negative topic, or if no negative topics exist
        passed = len(addressed_topics) > 0 or len(restoration_topics) == 0
        
        return {
            "passed": passed,
            "reason": (
                f"Page addresses {len(addressed_topics)} of {len(restoration_topics)} negative sentiment topics"
                if restoration_topics
                else "No negative sentiment topics to address"
            ),
            "details": {
                "addressed_topics": addressed_topics,
                "restoration_topics": restoration_topics,
                "overall_sentiment": sentiment_data.get("overall_sentiment"),
            },
        }
    
    async def _extract_page_topics(self, page: Page) -> List[str]:
        """Extract topics from page content."""
        topics = []
        
        # Extract from governance_checks entities
        if page.governance_checks:
            entities = page.governance_checks.get("entities", [])
            for entity in entities:
                entity_name = entity.get("name", "")
                if entity_name:
                    topics.append(entity_name)
        
        # Could also extract from page title/body using NLP
        if page.title:
            topics.append(page.title)
        
        return topics

