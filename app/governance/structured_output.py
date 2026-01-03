"""Week 5: Structured Output Generator - AI writes only what it's allowed to."""
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from openai import AsyncOpenAI


class StructuredContent(BaseModel):
    """Structured content output schema enforced by AI."""
    
    body: str = Field(..., description="Main content body (500-50,000 characters)")
    entities: List[str] = Field(default_factory=list, description="List of entities mentioned in content")
    faqs: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of FAQ items with 'question' and 'answer' keys (minimum 3 required)"
    )
    links: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of links with 'url' and 'anchor_text' keys. URLs must be valid and not hallucinated."
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class StructuredOutputGenerator:
    """
    Week 5: Structured Output Generator
    
    Enforces structured output using OpenAI's structured outputs feature.
    AI can only write what's allowed by the schema.
    """
    
    def __init__(self, openai_client: AsyncOpenAI):
        self.client = openai_client
    
    def get_content_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for structured content output.
        
        Returns:
            JSON schema dictionary for OpenAI structured outputs
        """
        return {
            "type": "object",
            "properties": {
                "body": {
                    "type": "string",
                    "description": "Main content body (500-50,000 characters)"
                },
                "entities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entities mentioned in content"
                },
                "faqs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"}
                        },
                        "required": ["question", "answer"]
                    },
                    "description": "List of FAQ items with 'question' and 'answer' keys (minimum 3 required)"
                },
                "links": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "format": "uri"},
                            "anchor_text": {"type": "string"}
                        },
                        "required": ["url", "anchor_text"]
                    },
                    "description": "List of links with 'url' and 'anchor_text' keys. URLs must be valid and not hallucinated."
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            },
            "required": ["body", "entities", "faqs", "links"]
        }
    
    def _extract_city_service(
        self,
        prompt: str,
        title: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract city and service from prompt, title, or metadata.
        
        Args:
            prompt: Content generation prompt
            title: Page title
            metadata: Optional metadata dict
            
        Returns:
            Tuple of (city, service) or (None, None) if not found
        """
        # Try metadata first
        if metadata:
            city = metadata.get("city") or metadata.get("location")
            service = metadata.get("service") or metadata.get("primary_service")
            if city and service:
                return (city, service)
        
        # Try to extract from title (common pattern: "Service in City")
        # e.g., "Plumbing Services in Austin" -> service="Plumbing Services", city="Austin"
        import re
        
        # Pattern: "Service in City" or "Service City"
        patterns = [
            r"(.+?)\s+in\s+([A-Z][a-zA-Z\s]+)",  # "Service in City"
            r"([A-Z][a-zA-Z\s]+)\s+(.+?)\s+services?",  # "City Service Services"
            r"(.+?)\s+services?\s+in\s+([A-Z][a-zA-Z\s]+)",  # "Service Services in City"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                if "in" in pattern:
                    service = match.group(1).strip()
                    city = match.group(2).strip()
                else:
                    city = match.group(1).strip()
                    service = match.group(2).strip()
                return (city, service)
        
        # Try to extract from prompt
        city_match = re.search(r"\b([A-Z][a-zA-Z\s]+(?:City|Town|County))\b", prompt, re.IGNORECASE)
        if city_match:
            city = city_match.group(1).strip()
            # Try to find service in prompt
            service_match = re.search(r"(plumbing|electrical|hvac|roofing|landscaping|legal|medical|dental)", prompt, re.IGNORECASE)
            service = service_match.group(1).strip() if service_match else None
            return (city, service)
        
        return (None, None)
    
    def _build_research_step_prompt(
        self,
        city: str,
        service: str,
    ) -> str:
        """
        Build the research step prompt for entity injection.
        
        Args:
            city: City name
            service: Service type
            
        Returns:
            Research step prompt string
        """
        return f"""CONTEXT: You are a local expert in {city} providing {service} services.

STEP 1: INTERNAL RESEARCH (Do not skip) Before writing the body content, identify and list the following for {city}:

1. 3 Major Neighborhoods or Suburbs (e.g., Hyde Park, Downtown).
2. 2 Specific Landmarks or recognizable buildings (e.g., The Art Museum, Central Station).
3. 1 Major Highway or Road artery used for service calls.

Constraint: Do not invent locations. If the city is too small to have landmarks, focus on the county or nearest major geographic feature. If you cannot verify landmarks with high confidence, default to mentioning the "County" instead of fake buildings.

STEP 2: CONTENT GENERATION Write the service page for {service} in {city}.

Integration: Do not just list the locations from Step 1. Weave them naturally into the narrative.

Bad: "We serve {city}. We also serve [Neighborhood1] and [Neighborhood2]."

Good: "Our trucks are frequently spotted on [Highway], heading from Downtown {city} out to residential jobs in [Neighborhood]."

Anti-Thinness Rule: Every mention of a location must be tied to the service. Explain why that location matters (e.g., "Older homes in [Neighborhood] often face specific plumbing issues like [Issue].")"""
    
    async def generate_structured_content(
        self,
        prompt: str,
        title: str,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StructuredContent:
        """
        Generate structured content using OpenAI structured outputs.
        
        Args:
            prompt: Content generation prompt
            title: Page title for context
            model: OpenAI model to use
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            metadata: Optional metadata dict (may contain city/service)
            
        Returns:
            StructuredContent instance with validated output
            
        Raises:
            ValueError: If structured output validation fails
        """
        # Extract city and service for automated entity injection
        city, service = self._extract_city_service(prompt, title, metadata)
        
        # Build base system prompt
        base_prompt = """You are a professional SEO content writer. Write comprehensive, well-structured content that preserves intent and authority.

Requirements:
1. Body must be 500-50,000 characters
2. Include at least 3 entities mentioned in the content
3. Include at least 3 FAQs with question and answer
4. Only include links to real, existing URLs (no hallucinated links)
5. All links must have valid URLs and descriptive anchor text

2025 SEO Alignment Requirements:
6. Start with a direct answer to the main question in the first 200 characters
7. Use bullet points (- or *) for key information (minimum 3 bullets)
8. Include clear section headings (## for H2, ### for H3, minimum 2 headings)
9. Add an FAQ section with at least 2 question-answer pairs
10. Demonstrate first-hand experience: Include specific data points, case studies, or real-world examples
11. Use structured formatting (lists, tables) for easy AI citation"""
        
        # Add research step if city/service are available
        if city and service:
            research_prompt = self._build_research_step_prompt(city, service)
            system_prompt = f"""{base_prompt}

{research_prompt}

Title: {title}"""
        else:
            system_prompt = f"""{base_prompt}

Title: {title}"""

        try:
            # Try using OpenAI structured outputs (beta API)
            # Note: This requires OpenAI Python SDK >= 1.0.0
            if hasattr(self.client.beta, 'chat') and hasattr(self.client.beta.chat.completions, 'parse'):
                response = await self.client.beta.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=StructuredContent,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                # Extract parsed content
                parsed_content = response.choices[0].message.parsed
                
                if parsed_content:
                    # Validate structured content
                    structured = StructuredContent(**parsed_content.model_dump())
                    return structured
            else:
                # Structured outputs API not available, use fallback
                raise AttributeError("Structured outputs API not available")
            
        except (AttributeError, Exception) as e:
            # Fallback to manual parsing if structured outputs not available
            # This handles cases where beta API might not be available
            return await self._generate_with_manual_parsing(
                prompt, title, model, temperature, max_tokens, metadata
            )
    
    async def _generate_with_manual_parsing(
        self,
        prompt: str,
        title: str,
        model: str,
        temperature: float,
        max_tokens: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StructuredContent:
        """
        Fallback: Generate content and manually parse into structured format.
        
        This is used when structured outputs API is not available.
        """
        # Extract city and service for automated entity injection
        city, service = self._extract_city_service(prompt, title, metadata)
        
        # Build base system prompt
        base_prompt = """You are a professional SEO content writer. Write comprehensive, well-structured content.

Return your response as a JSON object with this exact structure:
{
    "body": "Main content (500-50,000 characters)",
    "entities": ["entity1", "entity2", ...],
    "faqs": [
        {"question": "...", "answer": "..."},
        ...
    ],
    "links": [
        {"url": "https://...", "anchor_text": "..."},
        ...
    ],
    "metadata": {}
}

Requirements:
- Body: 500-50,000 characters
- Entities: At least 3 entities
- FAQs: At least 3 FAQs with question and answer
- Links: Only real URLs, no hallucinated links

2025 SEO Alignment Requirements:
- Start with a direct answer to the main question in the first 200 characters
- Use bullet points (- or *) for key information (minimum 3 bullets)
- Include clear section headings (## for H2, ### for H3, minimum 2 headings)
- Demonstrate first-hand experience: Include specific data points, case studies, or real-world examples
- Use structured formatting (lists, tables) for easy AI citation"""
        
        # Add research step if city/service are available
        if city and service:
            research_prompt = self._build_research_step_prompt(city, service)
            system_prompt = f"""{base_prompt}

{research_prompt}

Title: {title}"""
        else:
            system_prompt = f"""{base_prompt}

Title: {title}"""

        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{prompt}\n\nReturn only valid JSON, no markdown formatting."}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        import json
        content_text = response.choices[0].message.content
        
        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            
            parsed_data = json.loads(content_text)
            return StructuredContent(**parsed_data)
            
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to parse AI output as structured content: {str(e)}")

