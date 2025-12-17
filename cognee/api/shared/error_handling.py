"""Standardized error handling for API responses.

Provides utilities for:
- Sanitizing error messages (hiding internal details)
- Generating correlation IDs for support
- Logging errors with full context
"""

import uuid
from typing import Optional, Type

from fastapi.responses import JSONResponse

from cognee.shared.logging_utils import get_logger

logger = get_logger("error_handling")

# Map of exception types to safe user-facing messages
SAFE_ERROR_MESSAGES: dict[Type[Exception], str] = {
    ValueError: "Invalid input provided",
    TypeError: "Invalid data type",
    PermissionError: "Access denied",
    FileNotFoundError: "Resource not found",
    KeyError: "Required field missing",
    ConnectionError: "Service temporarily unavailable",
    TimeoutError: "Request timed out",
}

# Default message for unmapped exceptions
DEFAULT_ERROR_MESSAGE = "An internal error occurred"


def create_error_response(
    error: Exception,
    status_code: int = 500,
    include_error_id: bool = True,
    log_level: str = "error",
) -> JSONResponse:
    """Create a sanitized error response.

    Logs the full error details server-side while returning
    only safe information to the client.

    Args:
        error: The exception that occurred
        status_code: HTTP status code for response
        include_error_id: Whether to include correlation ID
        log_level: Logging level (error, warning, info)

    Returns:
        JSONResponse with sanitized error content
    """
    # Generate correlation ID
    error_id = str(uuid.uuid4())[:8] if include_error_id else None

    # Log full error details
    log_func = getattr(logger, log_level, logger.error)
    if error_id:
        log_func(f"Error {error_id}: {type(error).__name__}: {error}", exc_info=True)
    else:
        log_func(f"{type(error).__name__}: {error}", exc_info=True)

    # Get safe message for client
    safe_message = SAFE_ERROR_MESSAGES.get(type(error), DEFAULT_ERROR_MESSAGE)

    # Build response content
    content = {"error": safe_message}
    if error_id:
        content["error_id"] = error_id

    return JSONResponse(status_code=status_code, content=content)


def create_validation_error_response(
    message: str,
    field: Optional[str] = None,
    status_code: int = 400,
) -> JSONResponse:
    """Create a validation error response.

    For expected validation errors where the message is safe to show.

    Args:
        message: User-safe error message
        field: Optional field name that caused the error
        status_code: HTTP status code (default: 400)

    Returns:
        JSONResponse with validation error details
    """
    content = {"error": message}
    if field:
        content["field"] = field

    return JSONResponse(status_code=status_code, content=content)
