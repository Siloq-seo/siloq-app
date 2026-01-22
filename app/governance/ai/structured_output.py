"""Week 5: Structured Output Generator - AI writes only what it's allowed to."""
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
import re
from app.core.config import settings


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
    
    def _get_content_scope(
        self,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Get content scope from metadata.
        
        Returns:
            'local' or 'national' or None
        """
        if not metadata:
            return None
        
        scope = metadata.get("scope") or metadata.get("content_scope")
        if scope:
            return str(scope).lower()
        
        return None
    
    def _get_brand_voice(
        self,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Get brand voice from metadata.
        
        Returns:
            'voice_expert', 'voice_neighbor', 'voice_hype', or None
        """
        if not metadata:
            return None
        
        voice = metadata.get("brand_voice") or metadata.get("voice")
        if voice:
            return str(voice).lower()
        
        return None
    
    def _get_voice_system_prompt(self, voice: str) -> str:
        """
        Get system prompt addition based on brand voice enum.
        
        Task 5: Tone Governance - Uses SUPPORTED_TONES from config instead of free-text.
        
        Args:
            voice: Brand voice enum value (AUTHORITY, NEIGHBOR, HYPE)
            
        Returns:
            Voice-specific prompt addition
        """
        # Normalize voice input
        voice_upper = voice.upper().strip()
        
        # Map old voice names to new ones for backward compatibility
        voice_mapping = {
            "VOICE_EXPERT": "AUTHORITY",
            "VOICE_NEIGHBOR": "NEIGHBOR",
            "VOICE_HYPE": "HYPE",
        }
        
        # Check if it's an old voice name
        if voice_upper in voice_mapping:
            voice_upper = voice_mapping[voice_upper]
        
        # Get tone from SUPPORTED_TONES dictionary
        if voice_upper in settings.SUPPORTED_TONES:
            tone_description = settings.SUPPORTED_TONES[voice_upper]
            return f"""Tone Guidelines ({voice_upper}):
{tone_description}"""
        
        # If voice not found, return empty (no tone guidance)
        return ""
    
    def _insert_image_placeholders(self, content: str) -> str:
        """
        Insert image placeholder tags every ~300 words.
        
        Args:
            content: Content body text
            
        Returns:
            Content with image placeholder tags inserted
        """
        # Split content into words
        words = content.split()
        word_count = len(words)
        
        # Don't insert if content is too short
        if word_count < 200:
            return content
        
        # Calculate number of placeholders needed (every ~300 words)
        placeholder_interval = 300
        num_placeholders = max(1, (word_count // placeholder_interval))
        
        # Split by paragraphs for better insertion points
        paragraphs = content.split('\n\n')
        
        result_parts = []
        current_word_count = 0
        placeholder_count = 0
        target_word_count = placeholder_interval
        
        for i, para in enumerate(paragraphs):
            para_words = len(para.split())
            result_parts.append(para)
            current_word_count += para_words
            
            # Insert placeholder if we've passed the threshold
            if current_word_count >= target_word_count and placeholder_count < num_placeholders:
                # Generate descriptive placeholder based on surrounding content
                # Use last few words of current paragraph for context
                para_words_list = para.split()
                context_words = para_words_list[-10:] if len(para_words_list) >= 10 else para_words_list
                context = " ".join(context_words)
                placeholder = f"\n\n[IMAGE_PLACEHOLDER: {context} - Add relevant image here]\n\n"
                result_parts.append(placeholder)
                placeholder_count += 1
                target_word_count = placeholder_interval * (placeholder_count + 1)
        
        return "\n\n".join(result_parts)
    
    def _build_national_use_case_prompt(
        self,
        service: str,
    ) -> str:
        """
        Build use case injection prompt for national scope.
        
        Args:
            service: Service/product type
            
        Returns:
            Use case prompt string
        """
        return f"""CONTEXT: You are providing {service} services/products for a national audience.

STEP 1: USE CASE IDENTIFICATION (Do not skip) Before writing the body content, identify and list use cases for {service}:

1. 3 Primary Use Cases (e.g., "Best for winter", "Formal wear", "Outdoor activities").
2. 2 Target Scenarios (e.g., "Professional settings", "Casual weekend wear").
3. 1 Key Benefit or Feature that differentiates this {service}.

Constraint: Do not mention specific cities or locations. Focus on use cases, scenarios, and benefits.

STEP 2: CONTENT GENERATION Write the content page for {service}.

Integration: Do not just list the use cases from Step 1. Weave them naturally into the narrative.

Bad: "This {service} is good for winter. It is also good for formal wear."

Good: "Designed for harsh winter conditions, this {service} features [specific feature] that makes it ideal for [use case]. When transitioning to formal settings, [specific benefit] ensures [outcome]."

Anti-Thinness Rule: Every mention of a use case must be tied to specific features or benefits. Explain why that use case matters (e.g., "[Use Case] requires [Feature] because [Reason].")"""
    
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
        # Get content scope from metadata
        scope = self._get_content_scope(metadata)
        
        # Extract city and service for automated entity injection (only if local scope)
        city, service = self._extract_city_service(prompt, title, metadata) if scope != "national" else (None, None)
        
        # Get brand voice for tone governance
        voice = self._get_brand_voice(metadata)
        voice_prompt = self._get_voice_system_prompt(voice) if voice else ""
        
        # Build base system prompt
        base_prompt = """You are a professional SEO content writer. Write comprehensive, well-structured content that preserves intent and authority.

Requirements:
1. Body must be 500-50,000 characters
2. Include at least 3 entities mentioned in the content
3. Include at least 3 FAQs with question and answer
4. Only include links to real, existing URLs (no hallucinated links)
5. All links must have valid URLs and descriptive anchor text
6. Insert [IMAGE_PLACEHOLDER: detailed description] tags approximately every 300 words to prevent visual thinness

2025 SEO Alignment Requirements:
7. Start with a direct answer to the main question in the first 200 characters
8. Use bullet points (- or *) for key information (minimum 3 bullets)
9. Include clear section headings (## for H2, ### for H3, minimum 2 headings)
10. Add an FAQ section with at least 2 question-answer pairs
11. Demonstrate first-hand experience: Include specific data points, case studies, or real-world examples
12. Use structured formatting (lists, tables) for easy AI citation"""
        
        # Add voice prompt if available
        if voice_prompt:
            base_prompt += f"\n\n{voice_prompt}"
        
        # Add scope-specific research step
        if scope == "local" and city and service:
            # Local scope: Use geo-logic (landmarks, neighborhoods)
            research_prompt = self._build_research_step_prompt(city, service)
            system_prompt = f"""{base_prompt}

{research_prompt}

Title: {title}"""
        elif scope == "national" and service:
            # National scope: Use use case injection (NO city insertion)
            use_case_prompt = self._build_national_use_case_prompt(service)
            system_prompt = f"""{base_prompt}

{use_case_prompt}

CRITICAL CONSTRAINT: Do NOT mention any specific cities, neighborhoods, or local landmarks. This is national content. Focus on use cases, scenarios, and benefits only.

Title: {title}"""
        else:
            # No scope or missing data: Use base prompt
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
                    
                    # Insert image placeholders
                    structured.body = self._insert_image_placeholders(structured.body)
                    
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
        # Get content scope from metadata
        scope = self._get_content_scope(metadata)
        
        # Extract city and service for automated entity injection (only if local scope)
        city, service = self._extract_city_service(prompt, title, metadata) if scope != "national" else (None, None)
        
        # Get brand voice for tone governance
        voice = self._get_brand_voice(metadata)
        voice_prompt = self._get_voice_system_prompt(voice) if voice else ""
        
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
- Insert [IMAGE_PLACEHOLDER: detailed description] tags approximately every 300 words to prevent visual thinness

2025 SEO Alignment Requirements:
- Start with a direct answer to the main question in the first 200 characters
- Use bullet points (- or *) for key information (minimum 3 bullets)
- Include clear section headings (## for H2, ### for H3, minimum 2 headings)
- Demonstrate first-hand experience: Include specific data points, case studies, or real-world examples
- Use structured formatting (lists, tables) for easy AI citation"""
        
        # Add voice prompt if available
        if voice_prompt:
            base_prompt += f"\n\n{voice_prompt}"
        
        # Add scope-specific research step
        if scope == "local" and city and service:
            # Local scope: Use geo-logic (landmarks, neighborhoods)
            research_prompt = self._build_research_step_prompt(city, service)
            system_prompt = f"""{base_prompt}

{research_prompt}

Title: {title}"""
        elif scope == "national" and service:
            # National scope: Use use case injection (NO city insertion)
            use_case_prompt = self._build_national_use_case_prompt(service)
            system_prompt = f"""{base_prompt}

{use_case_prompt}

CRITICAL CONSTRAINT: Do NOT mention any specific cities, neighborhoods, or local landmarks. This is national content. Focus on use cases, scenarios, and benefits only.

Title: {title}"""
        else:
            # No scope or missing data: Use base prompt
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
            structured = StructuredContent(**parsed_data)
            
            # Insert image placeholders
            structured.body = self._insert_image_placeholders(structured.body)
            
            return structured
            
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to parse AI output as structured content: {str(e)}")

