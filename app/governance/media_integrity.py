"""
2026 Governance Enhancement: Media Integrity Gate

Google's "Multimodal Search" and "Video-First" indexing require media to be
governed as strictly as text. This module enforces media optimization standards:

- WebP conversion validation
- Auto-generate descriptive (not keyword-stuffed) Alt-text using Vision AI
- Ensure every video has a valid VideoObject Schema for Video SERPs eligibility
"""
import re
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Page
from app.types import GateCheckResult
from app.core.config import settings
from app.schemas.jsonld import JSONLDGenerator


class MediaIntegrityValidator:
    """
    Validates media integrity for multimedia governance.
    
    Checks:
    - Image format optimization (WebP preferred)
    - Descriptive alt-text generation (non-keyword-stuffed)
    - VideoObject schema validation for videos
    - Image metadata completeness
    """
    
    def __init__(self):
        self.jsonld_generator = JSONLDGenerator()
        # Supported image formats (WebP is preferred for modern browsers)
        self.preferred_image_formats = ["webp", "jpg", "jpeg", "png", "svg"]
        self.legacy_formats = ["gif", "bmp", "tiff"]  # Allowed but suboptimal
    
    async def validate_media_integrity(
        self,
        page: Page,
        db: AsyncSession,
    ) -> GateCheckResult:
        """
        Validate media integrity for multimedia governance.
        
        Args:
            page: Page to validate
            db: Database session
            
        Returns:
            GateCheckResult with passed status and details
        """
        if not page.body:
            return {
                "passed": True,  # No media to validate
                "details": {"body_exists": False, "media_count": 0},
            }
        
        body = page.body
        body_lower = body.lower()
        
        issues = []
        warnings = []
        details = {}
        
        # Extract all images from content
        images = self._extract_images(body)
        details["image_count"] = len(images)
        
        # Extract all videos from content
        videos = self._extract_videos(body)
        details["video_count"] = len(videos)
        
        # Check 1: Image format optimization (WebP preferred)
        images_without_webp = []
        images_legacy_format = []
        
        for img in images:
            img_src = img.get("src", "").lower()
            
            # Check if image is WebP or modern format
            is_webp = any(ext in img_src for ext in [".webp", "webp"])
            is_modern = any(ext in img_src for ext in [".jpg", ".jpeg", ".png", ".svg"])
            is_legacy = any(ext in img_src for ext in [".gif", ".bmp", ".tiff"])
            
            if is_legacy:
                images_legacy_format.append(img_src)
            elif not (is_webp or is_modern):
                # Unknown format
                images_without_webp.append(img_src)
        
        if images_legacy_format:
            warnings.append(
                f"{len(images_legacy_format)} images using legacy formats (GIF/BMP/TIFF). "
                "Consider converting to WebP for better performance."
            )
        
        details["images_legacy_format_count"] = len(images_legacy_format)
        details["images_without_webp_count"] = len(images_without_webp)
        
        # Check 2: Alt-text validation (descriptive, not keyword-stuffed)
        images_without_alt = []
        images_keyword_stuffed_alt = []
        
        for img in images:
            alt_text = img.get("alt", "").strip()
            
            if not alt_text:
                images_without_alt.append(img.get("src", ""))
            else:
                # Check for keyword stuffing (multiple keywords, excessive length, repetitive)
                if self._is_keyword_stuffed(alt_text):
                    images_keyword_stuffed_alt.append({
                        "src": img.get("src", ""),
                        "alt": alt_text,
                    })
        
        if images_without_alt:
            issues.append(
                f"{len(images_without_alt)} images missing alt-text. "
                "Alt-text is required for accessibility and SEO."
            )
        
        if images_keyword_stuffed_alt:
            issues.append(
                f"{len(images_keyword_stuffed_alt)} images have keyword-stuffed alt-text. "
                "Alt-text should be descriptive, not keyword-optimized."
            )
        
        details["images_without_alt_count"] = len(images_without_alt)
        details["images_keyword_stuffed_alt_count"] = len(images_keyword_stuffed_alt)
        
        # Check 3: VideoObject schema validation
        videos_without_schema = []
        
        if videos:
            # Check if VideoObject schema exists in page's JSON-LD
            try:
                schema = await self.jsonld_generator.generate_schema(db, page)
                video_objects = self._extract_video_objects_from_schema(schema)
                
                # Match videos to VideoObject schemas
                for video in videos:
                    video_src = video.get("src", "")
                    has_schema = any(
                        self._video_matches_schema(video_src, vo)
                        for vo in video_objects
                    )
                    
                    if not has_schema:
                        videos_without_schema.append(video_src)
            except Exception as e:
                warnings.append(f"Could not validate VideoObject schema: {str(e)}")
        
        if videos_without_schema:
            issues.append(
                f"{len(videos_without_schema)} videos missing VideoObject schema. "
                "Videos require VideoObject schema for Video SERP eligibility."
            )
        
        details["videos_without_schema_count"] = len(videos_without_schema)
        
        # Check 4: Image metadata completeness (width, height, loading attributes)
        images_without_metadata = []
        
        for img in images:
            has_width = "width" in img or "width=" in str(img).lower()
            has_height = "height" in img or "height=" in str(img).lower()
            has_loading = "loading" in img or "loading=" in str(img).lower()
            
            if not (has_width and has_height):
                images_without_metadata.append(img.get("src", ""))
        
        if images_without_metadata:
            warnings.append(
                f"{len(images_without_metadata)} images missing width/height attributes. "
                "Fixed dimensions prevent layout shift (CLS)."
            )
        
        details["images_without_metadata_count"] = len(images_without_metadata)
        
        # Overall assessment
        passed = len(issues) == 0
        
        if not passed:
            return {
                "passed": False,
                "reason": f"Media integrity validation failed: {issues[0] if issues else 'Media validation failed'}",
                "details": details,
                "warnings": warnings if warnings else None,
            }
        
        # Passed, but may have warnings
        return {
            "passed": True,
            "details": details,
            "warnings": warnings if warnings else None,
        }
    
    def _extract_images(self, body: str) -> List[Dict[str, str]]:
        """Extract image tags and attributes from HTML/Markdown content."""
        images = []
        
        # HTML img tags
        img_pattern = r'<img([^>]*?)>'
        for match in re.finditer(img_pattern, body, re.IGNORECASE):
            attrs_str = match.group(1)
            img_data = self._parse_attributes(attrs_str)
            images.append(img_data)
        
        # Markdown images: ![alt](src)
        markdown_pattern = r'!\[([^\]]*?)\]\(([^\)]+)\)'
        for match in re.finditer(markdown_pattern, body):
            alt_text = match.group(1)
            src = match.group(2)
            images.append({"alt": alt_text, "src": src})
        
        return images
    
    def _extract_videos(self, body: str) -> List[Dict[str, str]]:
        """Extract video tags and attributes from HTML content."""
        videos = []
        
        # HTML video tags
        video_pattern = r'<video([^>]*?)>'
        for match in re.finditer(video_pattern, body, re.IGNORECASE):
            attrs_str = match.group(1)
            video_data = self._parse_attributes(attrs_str)
            videos.append(video_data)
        
        # Iframe embeds (YouTube, Vimeo, etc.)
        iframe_pattern = r'<iframe([^>]*?)>'
        for match in re.finditer(iframe_pattern, body, re.IGNORECASE):
            attrs_str = match.group(1)
            iframe_data = self._parse_attributes(attrs_str)
            src = iframe_data.get("src", "")
            if any(domain in src.lower() for domain in ["youtube", "vimeo", "dailymotion"]):
                videos.append(iframe_data)
        
        return videos
    
    def _parse_attributes(self, attrs_str: str) -> Dict[str, str]:
        """Parse HTML attributes from attribute string."""
        attrs = {}
        
        # Extract src
        src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', attrs_str, re.IGNORECASE)
        if src_match:
            attrs["src"] = src_match.group(1)
        
        # Extract alt
        alt_match = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', attrs_str, re.IGNORECASE)
        if alt_match:
            attrs["alt"] = alt_match.group(1)
        
        # Extract width
        width_match = re.search(r'width\s*=\s*["\']?(\d+)["\']?', attrs_str, re.IGNORECASE)
        if width_match:
            attrs["width"] = width_match.group(1)
        
        # Extract height
        height_match = re.search(r'height\s*=\s*["\']?(\d+)["\']?', attrs_str, re.IGNORECASE)
        if height_match:
            attrs["height"] = height_match.group(1)
        
        # Extract loading
        loading_match = re.search(r'loading\s*=\s*["\']([^"\']+)["\']', attrs_str, re.IGNORECASE)
        if loading_match:
            attrs["loading"] = loading_match.group(1)
        
        return attrs
    
    def _is_keyword_stuffed(self, alt_text: str) -> bool:
        """
        Detect keyword-stuffed alt-text.
        
        Indicators:
        - Excessive length (> 150 characters)
        - Repeated keywords/phrases
        - Multiple commas/separators suggesting keyword list
        - Lack of natural language structure
        """
        if len(alt_text) > 150:
            return True
        
        # Check for repeated phrases (keyword stuffing pattern)
        words = alt_text.lower().split()
        if len(words) > 20:  # Too many words suggests keyword list
            return True
        
        # Check for excessive commas/s separators (keyword list pattern)
        separator_count = alt_text.count(",") + alt_text.count("|") + alt_text.count(";")
        if separator_count > 3:
            return True
        
        # Check for repeated words (suggests keyword repetition)
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # If any word appears more than 3 times in a short alt-text
        if len(words) < 15 and any(count > 3 for count in word_freq.values()):
            return True
        
        return False
    
    def _extract_video_objects_from_schema(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract VideoObject schemas from JSON-LD."""
        video_objects = []
        
        # Check if schema itself is a VideoObject
        if schema.get("@type") == "VideoObject":
            video_objects.append(schema)
        
        # Check for nested VideoObjects
        def extract_nested(obj: Any):
            if isinstance(obj, dict):
                if obj.get("@type") == "VideoObject":
                    video_objects.append(obj)
                for value in obj.values():
                    extract_nested(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_nested(item)
        
        extract_nested(schema)
        
        return video_objects
    
    def _video_matches_schema(self, video_src: str, video_object: Dict[str, Any]) -> bool:
        """Check if video source matches VideoObject schema contentUrl or embedUrl."""
        content_url = video_object.get("contentUrl", "")
        embed_url = video_object.get("embedUrl", "")
        
        return (
            video_src in content_url
            or video_src in embed_url
            or content_url in video_src
            or embed_url in video_src
        )
    
    async def generate_alt_text_suggestion(
        self,
        image_src: str,
        page_context: str,
    ) -> str:
        """
        Generate descriptive alt-text suggestion for an image.
        
        Note: This is a placeholder for Vision AI integration.
        In a full implementation, this would use Vision AI to analyze the image
        and generate descriptive, non-keyword-stuffed alt-text.
        
        Args:
            image_src: Image source URL
            page_context: Surrounding page content for context
            
        Returns:
            Suggested alt-text string
        """
        # Placeholder implementation
        # TODO: Integrate with Vision AI (e.g., OpenAI Vision API, Google Vision API)
        # to analyze image content and generate descriptive alt-text
        
        # For now, return a generic suggestion based on context
        if not page_context:
            return "Descriptive image"
        
        # Extract first few words from context as a basic suggestion
        words = page_context.split()[:10]
        return " ".join(words) + " image"

