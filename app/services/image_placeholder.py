"""Image Engine Fallback - Section 15
Simple utility to inject standardized image placeholder tags when AI generates content that requires visual aid.
This allows us to bulk-generate text now and "swap" images in later without breaking the layout.
"""
import re
from typing import List, Tuple, Optional


class ImagePlaceholderInjector:
    """
    Injects standardized image placeholder tags into content.
    
    Format: [[IMAGE_PROMPT: Describing a professional plumbing van in a suburban driveway]]
    """
    
    IMAGE_TAG_PATTERN = r'\[\[IMAGE_PROMPT:\s*(.+?)\]\]'
    WORDS_PER_IMAGE = 400  # Target: one image per 400 words
    
    @staticmethod
    def inject_image_placeholders(content: str, context: Optional[str] = None) -> str:
        """
        Inject image placeholder tags into content when visual aid is needed.
        
        Args:
            content: Content body text
            context: Optional context for generating image descriptions
            
        Returns:
            Content with image placeholder tags inserted
        """
        # Check if content already has image tags
        existing_tags = re.findall(ImagePlaceholderInjector.IMAGE_TAG_PATTERN, content)
        if existing_tags:
            # Content already has image tags, return as-is
            return content
        
        # Split content into words
        words = content.split()
        word_count = len(words)
        
        # Don't insert if content is too short
        if word_count < ImagePlaceholderInjector.WORDS_PER_IMAGE:
            return content
        
        # Calculate number of placeholders needed
        num_placeholders = max(1, word_count // ImagePlaceholderInjector.WORDS_PER_IMAGE)
        
        # Split by paragraphs for better insertion points
        paragraphs = content.split('\n\n')
        
        result_parts = []
        current_word_count = 0
        placeholder_count = 0
        target_word_count = ImagePlaceholderInjector.WORDS_PER_IMAGE
        
        for i, para in enumerate(paragraphs):
            para_words = len(para.split())
            result_parts.append(para)
            current_word_count += para_words
            
            # Insert placeholder if we've passed the threshold
            if current_word_count >= target_word_count and placeholder_count < num_placeholders:
                # Generate descriptive placeholder based on surrounding content
                image_description = ImagePlaceholderInjector._generate_image_description(
                    para, context
                )
                placeholder = f"\n\n[[IMAGE_PROMPT: {image_description}]]\n\n"
                result_parts.append(placeholder)
                placeholder_count += 1
                target_word_count = ImagePlaceholderInjector.WORDS_PER_IMAGE * (placeholder_count + 1)
        
        return "\n\n".join(result_parts)
    
    @staticmethod
    def _generate_image_description(paragraph: str, context: Optional[str] = None) -> str:
        """
        Generate a descriptive image prompt based on paragraph content.
        
        Args:
            paragraph: Paragraph text to analyze
            context: Optional context for better descriptions
            
        Returns:
            Image description string
        """
        # Extract key nouns and verbs from paragraph
        words = paragraph.split()
        
        # Look for key terms (simplified - in production, use NLP)
        key_terms = []
        for word in words[:20]:  # First 20 words
            # Remove punctuation
            clean_word = re.sub(r'[^\w\s]', '', word)
            if len(clean_word) > 4:  # Focus on longer, more descriptive words
                key_terms.append(clean_word.lower())
        
        # Build description
        if key_terms:
            description = f"Professional image related to {', '.join(key_terms[:3])}"
        else:
            description = "Professional image relevant to the content"
        
        # Add context if available
        if context:
            description = f"{description} in context of {context}"
        
        return description
    
    @staticmethod
    def extract_image_tags(content: str) -> List[Tuple[str, str]]:
        """
        Extract all image placeholder tags from content.
        
        Args:
            content: Content with image tags
            
        Returns:
            List of tuples (tag, description)
        """
        matches = re.finditer(ImagePlaceholderInjector.IMAGE_TAG_PATTERN, content)
        return [(match.group(0), match.group(1)) for match in matches]
    
    @staticmethod
    def replace_image_tag(content: str, old_tag: str, new_image_url: str, alt_text: str = "") -> str:
        """
        Replace an image placeholder tag with actual image HTML.
        
        Args:
            content: Content with image tags
            old_tag: The image tag to replace (e.g., "[[IMAGE_PROMPT: ...]]")
            new_image_url: URL of the actual image
            alt_text: Alt text for the image (defaults to description from tag)
            
        Returns:
            Content with tag replaced by image HTML
        """
        # Extract description from tag if alt_text not provided
        if not alt_text:
            match = re.search(ImagePlaceholderInjector.IMAGE_TAG_PATTERN, old_tag)
            if match:
                alt_text = match.group(1)
        
        # Replace tag with image HTML
        image_html = f'<img src="{new_image_url}" alt="{alt_text}" loading="lazy" />'
        return content.replace(old_tag, image_html)
    
    @staticmethod
    def has_image_tags(content: str) -> bool:
        """
        Check if content has any image placeholder tags.
        
        Args:
            content: Content to check
            
        Returns:
            True if content has image tags, False otherwise
        """
        return bool(re.search(ImagePlaceholderInjector.IMAGE_TAG_PATTERN, content))
    
    @staticmethod
    def count_image_tags(content: str) -> int:
        """
        Count the number of image placeholder tags in content.
        
        Args:
            content: Content to check
            
        Returns:
            Number of image tags found
        """
        return len(re.findall(ImagePlaceholderInjector.IMAGE_TAG_PATTERN, content))

