"""Shared API utilities."""

from .error_handling import (
    create_error_response,
    create_validation_error_response,
)

__all__ = [
    "create_error_response",
    "create_validation_error_response",
]
