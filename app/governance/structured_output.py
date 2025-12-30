"""Week 5: Structured Output Generator - AI writes only what it's allowed to."""
from typing import Dict, List, Optional, Any
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
    
    async def generate_structured_content(
        self,
        prompt: str,
        title: str,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> StructuredContent:
        """
        Generate structured content using OpenAI structured outputs.
        
        Args:
            prompt: Content generation prompt
            title: Page title for context
            model: OpenAI model to use
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            StructuredContent instance with validated output
            
        Raises:
            ValueError: If structured output validation fails
        """
        system_prompt = f"""You are a professional SEO content writer. Write comprehensive, well-structured content that preserves intent and authority.

Requirements:
1. Body must be 500-50,000 characters
2. Include at least 3 entities mentioned in the content
3. Include at least 3 FAQs with question and answer
4. Only include links to real, existing URLs (no hallucinated links)
5. All links must have valid URLs and descriptive anchor text

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
                prompt, title, model, temperature, max_tokens
            )
    
    async def _generate_with_manual_parsing(
        self,
        prompt: str,
        title: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> StructuredContent:
        """
        Fallback: Generate content and manually parse into structured format.
        
        This is used when structured outputs API is not available.
        """
        system_prompt = f"""You are a professional SEO content writer. Write comprehensive, well-structured content.

Return your response as a JSON object with this exact structure:
{{
    "body": "Main content (500-50,000 characters)",
    "entities": ["entity1", "entity2", ...],
    "faqs": [
        {{"question": "...", "answer": "..."}},
        ...
    ],
    "links": [
        {{"url": "https://...", "anchor_text": "..."}},
        ...
    ],
    "metadata": {{}}
}}

Requirements:
- Body: 500-50,000 characters
- Entities: At least 3 entities
- FAQs: At least 3 FAQs with question and answer
- Links: Only real URLs, no hallucinated links

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

