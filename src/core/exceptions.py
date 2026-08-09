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
    ERROR_BAD_REQUEST,
    ERROR_CONFLICT,
    ERROR_DOMAIN,
    ERROR_FORBIDDEN,
    ERROR_INTERNAL_SERVER_ERROR,
    ERROR_NOT_FOUND,
    ERROR_PERSISTENCE,
    ERROR_UNAUTHORIZED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
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
    error_code: str = ERROR_INTERNAL_SERVER_ERROR
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
        detail: str | None = None,
    ):
        super().__init__(message)

        if status_code is not None:
            self.status_code = status_code

        if error_code is not None:
            self.error_code = error_code

        self.message = message or self.default_message
        self.detail = detail or self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


class BadRequestError(AppError):
    """
    HTTP 400 Bad Request.
    """

    def __init__(
        self,
        *,
        message: str,
        error_code: str = ERROR_BAD_REQUEST,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=HTTP_400_BAD_REQUEST,
        )


class NotFoundError(AppError):
    """
    HTTP 404 Not Found.
    """

    def __init__(
        self,
        *,
        message: str,
        error_code: str = ERROR_NOT_FOUND,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=HTTP_404_NOT_FOUND,
        )


class ConflictError(AppError):
    """
    HTTP 409 Conflict.
    """

    def __init__(
        self,
        *,
        message: str,
        error_code: str = ERROR_CONFLICT,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=HTTP_409_CONFLICT,
        )


class UnauthorizedError(AppError):
    """
    HTTP 401 Unauthorized.
    """

    def __init__(
        self,
        *,
        message: str = "Unauthorized.",
        error_code: str = ERROR_UNAUTHORIZED,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppError):
    """
    HTTP 403 Forbidden.
    """

    def __init__(
        self,
        *,
        message: str = "Forbidden.",
        error_code: str = ERROR_FORBIDDEN,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=HTTP_403_FORBIDDEN,
        )


class InternalServerError(AppError):
    """
    HTTP 500 Internal Server Error.
    """

    def __init__(
        self,
        *,
        message: str = "Internal server error.",
        error_code: str = ERROR_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


class DomainError(AppError):
    """
    Base class for domain-level business rule violations.

    Domain errors represent expected, client-visible failures such as
    validation issues or missing resources. These errors typically map
    to 4xx HTTP status codes.
    """

    status_code: int = HTTP_400_BAD_REQUEST
    error_code: str = ERROR_DOMAIN


class PersistenceError(AppError):
    """
    Raised when a database or persistence operation fails.

    This error indicates an internal system failure and should never
    expose implementation details to API clients.
    """

    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    error_code = ERROR_PERSISTENCE


class ConfigurationError(AppError):
    """Bad or missing configuration."""


class DatabaseError(AppError):
    """Any database operation failure."""


class CacheError(AppError):
    """Cache backend failure."""


class ValidationError(AppError):
    """Input validation failure."""


class UserAlreadyExistsError(ConflictError):
    """
    Raised when a user with the same email already exists.
    """

    def __init__(self, message: str = "User already exists.") -> None:
        super().__init__(
            message=message,
            error_code="USER_ALREADY_EXISTS",
        )


class UserNotFoundError(NotFoundError):
    """
    Raised when a user cannot be found.
    """

    def __init__(self, message: str = "User not found.") -> None:
        super().__init__(
            message=message,
            error_code="USER_NOT_FOUND",
        )
