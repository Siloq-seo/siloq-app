"""API Helper utilities - Re-exported from utils module for backward compatibility"""
# These functions have been moved to app.utils for better organization
# Re-export here to maintain backward compatibility with existing code
from app.utils.database import get_or_404, get_or_none
from app.utils.responses import format_error_response, format_success_response

__all__ = [
    "get_or_404",
    "get_or_none",
    "format_error_response",
    "format_success_response",
]
