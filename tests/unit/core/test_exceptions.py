"""
Unit tests for application exceptions.
"""

from __future__ import annotations

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
from src.core.exceptions.authorization import AuthorizationError
from src.core.exceptions.base import AppError, DomainError
from src.core.exceptions.database import DatabaseError
from src.core.exceptions.httpx import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from src.core.exceptions.infrastructure import (
    CacheError,
    ConfigurationError,
    PersistenceError,
)
from src.core.exceptions.validation import ValidationError


def test_app_error_uses_defaults() -> None:
    """
    It should use the default values.
    """

    error = AppError(
        message="Something went wrong.",
    )

    assert error.message == "Something went wrong."
    assert error.detail == "Something went wrong."
    assert error.status_code == HTTP_500_INTERNAL_SERVER_ERROR
    assert error.error_code == ERROR_INTERNAL_SERVER_ERROR


def test_app_error_overrides_defaults() -> None:
    """
    It should allow overriding the status code and error code.
    """

    error = AppError(
        message="Boom",
        status_code=418,
        error_code="TEAPOT",
        detail="Custom detail",
    )

    assert error.status_code == 418
    assert error.error_code == "TEAPOT"
    assert error.detail == "Custom detail"


def test_app_error_repr() -> None:
    """
    It should return a useful representation.
    """

    error = AppError(
        message="Boom",
    )

    assert repr(error) == "AppError(message='Boom', error_code='INTERNAL_SERVER_ERROR')"


def test_bad_request_error() -> None:
    """
    It should create a bad request error.
    """

    error = BadRequestError(
        message="Invalid request.",
    )

    assert error.status_code == HTTP_400_BAD_REQUEST
    assert error.error_code == ERROR_BAD_REQUEST
    assert error.message == "Invalid request."


def test_not_found_error() -> None:
    """
    It should create a not found error.
    """

    error = NotFoundError(
        message="Missing.",
    )

    assert error.status_code == HTTP_404_NOT_FOUND
    assert error.error_code == ERROR_NOT_FOUND
    assert error.message == "Missing."


def test_conflict_error() -> None:
    """
    It should create a conflict error.
    """

    error = ConflictError(
        message="Conflict.",
    )

    assert error.status_code == HTTP_409_CONFLICT
    assert error.error_code == ERROR_CONFLICT
    assert error.message == "Conflict."


def test_unauthorized_error() -> None:
    """
    It should create an unauthorized error.
    """

    error = UnauthorizedError()

    assert error.status_code == HTTP_401_UNAUTHORIZED
    assert error.error_code == ERROR_UNAUTHORIZED
    assert error.message == "Unauthorized."


def test_forbidden_error() -> None:
    """
    It should create a forbidden error.
    """

    error = ForbiddenError()

    assert error.status_code == HTTP_403_FORBIDDEN
    assert error.error_code == ERROR_FORBIDDEN
    assert error.message == "Forbidden."


def test_domain_error_defaults() -> None:
    """
    It should expose the default domain error values.
    """

    error = DomainError(
        message="Validation failed.",
    )

    assert error.status_code == HTTP_400_BAD_REQUEST
    assert error.error_code == ERROR_DOMAIN
    assert error.message == "Validation failed."


def test_persistence_error_defaults() -> None:
    """
    It should expose the default persistence error values.
    """

    error = PersistenceError(
        message="Database failed.",
    )

    assert error.status_code == HTTP_500_INTERNAL_SERVER_ERROR
    assert error.error_code == ERROR_PERSISTENCE
    assert error.message == "Database failed."


def test_configuration_error_is_app_error() -> None:
    """
    It should inherit from AppError.
    """

    error = ConfigurationError(
        "Invalid configuration.",
    )

    assert isinstance(
        error,
        AppError,
    )


def test_database_error_is_app_error() -> None:
    """
    It should inherit from AppError.
    """

    error = DatabaseError(
        "Database failed.",
    )

    assert isinstance(
        error,
        AppError,
    )


def test_cache_error_is_app_error() -> None:
    """
    It should inherit from AppError.
    """

    error = CacheError(
        "Cache failed.",
    )

    assert isinstance(
        error,
        AppError,
    )


def test_validation_error_is_app_error() -> None:
    """
    It should inherit from AppError.
    """

    error = ValidationError(
        "Validation failed.",
    )

    assert isinstance(
        error,
        AppError,
    )


def test_user_already_exists_error() -> None:
    """
    It should create a user already exists error.
    """

    error = UserAlreadyExistsError()

    assert error.status_code == HTTP_409_CONFLICT
    assert error.error_code == "USER_ALREADY_EXISTS"
    assert error.message == "User already exists."


def test_user_not_found_error() -> None:
    """
    It should create a user not found error.
    """

    error = UserNotFoundError()

    assert error.status_code == HTTP_404_NOT_FOUND
    assert error.error_code == "USER_NOT_FOUND"
    assert error.message == "User not found."


def test_authorization_error_default_message() -> None:
    error = AuthorizationError()

    assert str(error) == "User is not authorized to perform this action."


def test_authorization_error_custom_message() -> None:
    error = AuthorizationError("User is not authorized to send emails.")

    assert str(error) == "User is not authorized to send emails."


def test_authorization_error_is_exception() -> None:
    assert issubclass(AuthorizationError, Exception)
