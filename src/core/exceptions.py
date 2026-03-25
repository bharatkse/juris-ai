"""
Application-level exception hierarchy.

This module defines all custom exceptions used across the service.
Exceptions are divided into:
- Domain errors: business-rule violations (mapped to 4xx responses)
- Infrastructure errors: persistence or system failures (mapped to 5xx responses)

These exceptions are intentionally HTTP-agnostic and are translated
to HTTP responses via global FastAPI exception handlers.
"""

from src.core.constants import (
    ERROR_DOMAIN,
    ERROR_INTERVAL_SERVER_ERROR,
    ERROR_NOT_FOUND,
    ERROR_PERSISTENCE,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)


class AppError(Exception):
    """
    Base application exception.

    All custom exceptions in the application should inherit from this class.
    It provides a common structure for error handling while remaining
    decoupled from FastAPI and transport-level concerns.

    Attributes:
        status_code: HTTP status code associated with the error
        error_code: Stable, application-specific error identifier
    """

    status_code: int = HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = ERROR_INTERVAL_SERVER_ERROR

    def __init__(self, message: str, status_code: int | None = None, error_code: str | None = None):
        super().__init__(message)

        if status_code is not None:
            self.status_code = status_code

        if error_code is not None:
            self.error_code = error_code


class DomainError(AppError):
    """
    Base class for domain-level business rule violations.

    Domain errors represent expected, client-visible failures such as
    validation issues or missing resources. These errors typically map
    to 4xx HTTP status codes.
    """

    status_code: int = HTTP_400_BAD_REQUEST
    error_code: str = ERROR_DOMAIN


class NotFoundError(DomainError):
    """
    Raised when a requested resource does not exist in the system.
    """

    status_code = HTTP_404_NOT_FOUND
    error_code = ERROR_NOT_FOUND


class PersistenceError(AppError):
    """
    Raised when a database or persistence operation fails.

    This error indicates an internal system failure and should never
    expose implementation details to API clients.
    """

    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    error_code = ERROR_PERSISTENCE
