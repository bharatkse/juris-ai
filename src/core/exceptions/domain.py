"""
Domain exceptions.

Domain exceptions represent expected business rule violations caused by
invalid client requests or application state.

These exceptions typically map to HTTP 4xx responses via the global
exception handlers.
"""

from __future__ import annotations

from src.core.constants import (
    ERROR_CONFLICT,
    ERROR_FORBIDDEN,
    ERROR_NOT_FOUND,
    ERROR_UNAUTHORIZED,
    ERROR_VALIDATION,
)
from src.core.exceptions.base import DomainError


class DomainValidationError(DomainError):
    """
    Raised when business/domain validation fails.

    Examples:
        - Invalid workflow transition
        - Missing required business field
        - Unsupported operation
    """

    error_code = ERROR_VALIDATION
    default_message = "Validation failed."


class ResourceNotFoundError(DomainError):
    """
    Raised when a requested resource does not exist.

    Examples:
        - User not found
        - Chat session not found
        - Contract not found
    """

    error_code = ERROR_NOT_FOUND
    default_message = "Requested resource was not found."


class ConflictError(DomainError):
    """
    Raised when an operation conflicts with the current resource state.

    Examples:
        - Duplicate resource
        - Already processed
        - Concurrent modification
    """

    error_code = ERROR_CONFLICT
    default_message = "Resource conflict."


class UnauthorizedError(DomainError):
    """
    Raised when authentication is required or has failed.
    """

    error_code = ERROR_UNAUTHORIZED
    default_message = "Authentication required."


class ForbiddenError(DomainError):
    """
    Raised when the authenticated user lacks permission to perform
    the requested operation.
    """

    error_code = ERROR_FORBIDDEN
    default_message = "Permission denied."
