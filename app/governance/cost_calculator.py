"""Week 5: Cost Calculator for AI API calls."""
from typing import Dict, Optional
from openai.types.chat import ChatCompletion


class CostCalculator:
    """
    Week 5: Calculate costs for OpenAI API calls.
    
    Pricing (as of 2024):
    - GPT-4 Turbo: $0.01/1K input tokens, $0.03/1K output tokens
    - GPT-4: $0.03/1K input tokens, $0.06/1K output tokens
    - GPT-3.5 Turbo: $0.0005/1K input tokens, $0.0015/1K output tokens
    - text-embedding-3-small: $0.02/1M tokens
    """
    
    # Pricing per 1K tokens (in USD)
    PRICING = {
        "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "text-embedding-3-small": {"input": 0.02 / 1000, "output": 0.0},  # Per 1M tokens
        "text-embedding-3-large": {"input": 0.13 / 1000, "output": 0.0},
    }
    
    @classmethod
    def calculate_chat_completion_cost(
        cls,
        response: ChatCompletion,
        model: str = "gpt-4-turbo-preview",
    ) -> float:
        """
        Calculate cost for a chat completion response.
        
        Args:
            response: OpenAI ChatCompletion response
            model: Model name used
            
        Returns:
            Cost in USD
        """
        if model not in cls.PRICING:
            # Default to GPT-4 Turbo pricing if unknown
            model = "gpt-4-turbo-preview"
        
        pricing = cls.PRICING[model]
        
        # Get token usage
        usage = response.usage
        if not usage:
            return 0.0
        
        input_tokens = usage.prompt_tokens or 0
        output_tokens = usage.completion_tokens or 0
        
        # Calculate cost
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    @classmethod
    def calculate_embedding_cost(
        cls,
        tokens: int,
        model: str = "text-embedding-3-small",
    ) -> float:
        """
        Calculate cost for embedding generation.
        
        Args:
            tokens: Number of tokens
            model: Embedding model name
            
        Returns:
            Cost in USD
        """
        if model not in cls.PRICING:
            model = "text-embedding-3-small"
        
        pricing = cls.PRICING[model]
        
        # Embedding pricing is per 1M tokens
        cost = (tokens / 1_000_000) * pricing["input"]
        
        return cost
    
    @classmethod
    def estimate_chat_completion_cost(
        cls,
        input_tokens: int,
        estimated_output_tokens: int,
        model: str = "gpt-4-turbo-preview",
    ) -> float:
        """
        Estimate cost before making API call.
        
        Args:
            input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
            model: Model name
            
        Returns:
            Estimated cost in USD
        """
        if model not in cls.PRICING:
            model = "gpt-4-turbo-preview"
        
        pricing = cls.PRICING[model]
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (estimated_output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost

