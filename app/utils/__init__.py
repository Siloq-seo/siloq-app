"""Shared utility functions and helpers"""
from app.utils.database import get_or_404, get_or_none
from app.utils.responses import format_error_response, format_success_response

__all__ = [
    "get_or_404",
    "get_or_none",
    "format_error_response",
    "format_success_response",
]
