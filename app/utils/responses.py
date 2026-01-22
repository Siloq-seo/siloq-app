"""Response formatting utilities"""
from typing import Optional


def format_error_response(message: str, error_code: Optional[str] = None, **kwargs) -> dict:
    """
    Format a standardized error response

    Args:
        message: Error message
        error_code: Optional error code
        **kwargs: Additional fields to include in response

    Returns:
        Dict with error details

    Example:
        return format_error_response(
            "Invalid input",
            error_code="VALIDATION_001",
            field="email"
        )
    """
    response = {"error": message}
    if error_code:
        response["error_code"] = error_code
    response.update(kwargs)
    return response


def format_success_response(message: str, data: Optional[dict] = None, **kwargs) -> dict:
    """
    Format a standardized success response

    Args:
        message: Success message
        data: Optional data payload
        **kwargs: Additional fields to include in response

    Returns:
        Dict with success details

    Example:
        return format_success_response(
            "Site created successfully",
            data={"site_id": str(site.id)}
        )
    """
    response = {"message": message}
    if data:
        response["data"] = data
    response.update(kwargs)
    return response
