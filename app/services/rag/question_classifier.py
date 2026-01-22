"""Question type classification for RAG knowledge gap detection"""
from enum import Enum
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

from app.core.config import settings


class QuestionType(str, Enum):
    """Question categories that must be answerable"""
    VENDOR = "vendor"  # Vendor/product questions
    BUSINESS = "business"  # Business model, operations questions
    CONTENT = "content"  # Content strategy, creation questions
    PRICING = "pricing"  # Pricing, packages, costs questions
    TECHNIQUE = "technique"  # How-to, methodology, technique questions
    MENTORSHIP = "mentorship"  # Guidance, advice, mentorship questions


class QuestionClassifier:
    """
    Classifies questions into categories to ensure knowledge base coverage.
    
    Prevents gaps by ensuring all question types can be answered.
    """
    
    def __init__(self, openai_client: Optional[AsyncOpenAI] = None):
        self.client = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Question type keywords for fast classification
        self.type_keywords = {
            QuestionType.VENDOR: [
                "vendor", "supplier", "product", "tool", "software", "platform",
                "service provider", "who provides", "what tool", "which vendor"
            ],
            QuestionType.BUSINESS: [
                "business model", "how do you make money", "revenue", "operations",
                "company", "organization", "team", "process", "workflow"
            ],
            QuestionType.CONTENT: [
                "content", "blog", "article", "writing", "copy", "strategy",
                "create content", "content marketing", "SEO content"
            ],
            QuestionType.PRICING: [
                "price", "cost", "pricing", "package", "plan", "subscription",
                "how much", "what does it cost", "fee", "payment"
            ],
            QuestionType.TECHNIQUE: [
                "how to", "how do", "technique", "method", "approach", "way to",
                "steps", "process", "tutorial", "guide", "best practice"
            ],
            QuestionType.MENTORSHIP: [
                "advice", "guidance", "mentor", "help me", "should I", "recommend",
                "suggest", "what should", "tips", "coaching"
            ],
        }
    
    async def classify(self, question: str) -> Dict[str, Any]:
        """
        Classify a question into one or more categories.
        
        Args:
            question: User question text
            
        Returns:
            {
                "primary_type": QuestionType,
                "secondary_types": List[QuestionType],
                "confidence": float,
                "keywords_matched": List[str]
            }
        """
        question_lower = question.lower()
        
        # Fast keyword-based classification
        type_scores: Dict[QuestionType, float] = {}
        matched_keywords: Dict[QuestionType, List[str]] = {}
        
        for qtype, keywords in self.type_keywords.items():
            score = 0.0
            matched = []
            
            for keyword in keywords:
                if keyword in question_lower:
                    score += 1.0
                    matched.append(keyword)
            
            if score > 0:
                type_scores[qtype] = score
                matched_keywords[qtype] = matched
        
        # If no keywords matched, use AI classification
        if not type_scores:
            return await self._ai_classify(question)
        
        # Sort by score
        sorted_types = sorted(type_scores.items(), key=lambda x: x[1], reverse=True)
        primary_type = sorted_types[0][0]
        primary_score = sorted_types[0][1]
        
        # Secondary types (score > 0.5 * primary)
        secondary_types = [
            qtype for qtype, score in sorted_types[1:]
            if score >= primary_score * 0.5
        ]
        
        # Calculate confidence (normalized score)
        max_possible_score = len(self.type_keywords[primary_type])
        confidence = min(primary_score / max_possible_score, 1.0)
        
        return {
            "primary_type": primary_type,
            "secondary_types": secondary_types,
            "confidence": confidence,
            "keywords_matched": matched_keywords.get(primary_type, []),
        }
    
    async def _ai_classify(self, question: str) -> Dict[str, Any]:
        """Use AI to classify question when keywords don't match"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Classify the question into one of these categories:
- vendor: Questions about vendors, products, tools, suppliers
- business: Questions about business model, operations, company
- content: Questions about content creation, strategy, writing
- pricing: Questions about costs, packages, pricing
- technique: Questions about how-to, methods, techniques
- mentorship: Questions asking for advice, guidance, recommendations

Respond with JSON: {"type": "category", "confidence": 0.0-1.0}"""
                    },
                    {"role": "user", "content": question}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            result = response.choices[0].message.content
            import json
            ai_result = json.loads(result)
            
            return {
                "primary_type": QuestionType(ai_result.get("type", "technique")),
                "secondary_types": [],
                "confidence": float(ai_result.get("confidence", 0.5)),
                "keywords_matched": [],
            }
        except Exception:
            # Fallback to technique (most common)
            return {
                "primary_type": QuestionType.TECHNIQUE,
                "secondary_types": [],
                "confidence": 0.3,
                "keywords_matched": [],
            }
    
    def get_all_types(self) -> List[QuestionType]:
        """Get all question types that must be covered"""
        return list(QuestionType)
