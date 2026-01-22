"""Unit tests for image placeholder service"""
import pytest
from app.services.media import ImagePlaceholderInjector


class TestImagePlaceholderInjector:
    """Tests for ImagePlaceholderInjector"""
    
    def test_inject_image_placeholders_short_content(self):
        """Test that short content doesn't get placeholders"""
        content = "Short content here."
        result = ImagePlaceholderInjector.inject_image_placeholders(content)
        
        assert result == content
        assert "IMAGE_PROMPT" not in result
    
    def test_inject_image_placeholders_long_content(self):
        """Test that long content gets placeholders"""
        # Create content with 500+ words
        content = " ".join(["word"] * 500)
        result = ImagePlaceholderInjector.inject_image_placeholders(content)
        
        assert "IMAGE_PROMPT" in result or len(result) > len(content)
    
    def test_extract_image_tags(self):
        """Test extracting image tags from content"""
        content = "Text [[IMAGE_PROMPT: A beautiful sunset]] more text"
        tags = ImagePlaceholderInjector.extract_image_tags(content)
        
        assert len(tags) > 0
        assert any("sunset" in tag[1].lower() for tag in tags)
    
    def test_has_image_tags(self):
        """Test checking if content has image placeholder tags"""
        content_with = "Text [[IMAGE_PROMPT: Description]] more text"
        content_without = "Just regular text here"
        
        assert ImagePlaceholderInjector.has_image_tags(content_with) is True
        assert ImagePlaceholderInjector.has_image_tags(content_without) is False
    
    def test_count_image_tags(self):
        """Test counting image tags in content"""
        content = "Text [[IMAGE_PROMPT: First]] more [[IMAGE_PROMPT: Second]] text"
        count = ImagePlaceholderInjector.count_image_tags(content)
        
        assert count == 2
    
    def test_replace_image_tag(self):
        """Test replacing image tag with HTML"""
        content = "Text [[IMAGE_PROMPT: A sunset]] more text"
        result = ImagePlaceholderInjector.replace_image_tag(
            content,
            "[[IMAGE_PROMPT: A sunset]]",
            "https://example.com/image.jpg",
            "Sunset image"
        )
        
        assert "IMAGE_PROMPT" not in result
        assert "image.jpg" in result
        assert "<img" in result
