"""
Base application exceptions.

Defines the root exception hierarchy shared across the application.

Hierarchy:

AppError
├── DomainError
├── InfrastructureError
└── AIError

Concrete exceptions should inherit from one of these base classes.
HTTP responses are produced by the application's global exception
handlers, keeping the exception hierarchy transport-agnostic.
"""

from __future__ import annotations

from src.core.constants import (
    ERROR_AI,
    ERROR_DOMAIN,
    ERROR_INFRASTRUCTURE,
    ERROR_INTERNAL_SERVER_ERROR,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)


class AppError(Exception):
    """
    Base application exception.

    All custom exceptions should inherit from this class.
    """

    status_code: int = HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = ERROR_INTERNAL_SERVER_ERROR
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        detail: str | None = None,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.detail = detail or self.message
        self.status_code = status_code or self.status_code

        if error_code is not None:
            self.error_code = error_code

        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r})"
        )


class DomainError(AppError):
    """
    Base class for business/domain rule violations.
    """

    status_code = HTTP_400_BAD_REQUEST
    error_code = ERROR_DOMAIN


class InfrastructureError(AppError):
    """
    Base class for infrastructure failures.
    """

    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    error_code = ERROR_INFRASTRUCTURE


class AIError(AppError):
    """
    Base class for AI subsystem failures.
    """

    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    error_code = ERROR_AI
