"""
Application-level exception hierarchy.

This module defines all custom exceptions used across the service.
Exceptions are divided into:
- Domain errors: business-rule violations (mapped to 4xx responses)
- Infrastructure errors: persistence or system failures (mapped to 5xx responses)

These exceptions are intentionally HTTP-agnostic and are translated
to HTTP responses via global FastAPI exception handlers.
"""

from core.constants import (
    ERROR_BAD_REQUEST,
    ERROR_CONFLICT,
    ERROR_FORBIDDEN,
    ERROR_NOT_FOUND,
    ERROR_UNAUTHORIZED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)
from core.exceptions.base import AppError


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


class ConversationInactiveError(ForbiddenError):
    """
    Raised when a conversation is inactive.
    """

    def __init__(self, message: str = "Conversation is inactive.") -> None:
        super().__init__(
            message=message,
            error_code="CONVERSATION_INACTIVE",
        )
