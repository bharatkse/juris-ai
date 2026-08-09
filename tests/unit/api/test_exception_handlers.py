"""
Unit tests for global exception handlers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from starlette.requests import Request

from src.api.exception_handlers import (
    domain_exception_handler,
    handle_app_error,
    persistence_exception_handler,
    register_exception_handlers,
    unhandled_exception_handler,
)
from src.core.constants import (
    ERROR_INTERNAL_SERVER_ERROR,
    ERROR_PERSISTENCE,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from src.core.exceptions import AppError, DomainError, PersistenceError


def build_request() -> Request:
    """
    Build a request instance.
    """

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        },
    )


@patch("src.api.exception_handlers.logger")
def test_domain_exception_handler(
    mock_logger: MagicMock,
) -> None:
    """
    It should return an API response for domain errors.
    """

    exception = DomainError(
        message="Conversation not found.",
    )

    response = domain_exception_handler(
        build_request(),
        exception,
    )

    assert response.status_code == exception.status_code

    body = response.body.decode()

    assert '"success":false' in body
    assert exception.error_code in body
    assert exception.message in body

    mock_logger.exception.assert_called_once_with(
        "Domain error occurred",
        extra={
            "error_code": exception.error_code,
            "detail": exception.message,
        },
    )


@patch("src.api.exception_handlers.logger")
def test_persistence_exception_handler(
    mock_logger: MagicMock,
) -> None:
    """
    It should return a generic persistence error response.
    """

    exception = PersistenceError(
        message="Database unavailable.",
    )

    response = persistence_exception_handler(
        build_request(),
        exception,
    )

    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    body = response.body.decode()

    assert '"success":false' in body
    assert ERROR_PERSISTENCE in body
    assert "Please try again in a few moments." in body

    mock_logger.exception.assert_called_once_with(
        "Persistence layer failure",
    )


@patch("src.api.exception_handlers.logger")
def test_handle_app_error(
    mock_logger: MagicMock,
) -> None:
    """
    It should return an API response for application errors.
    """

    exception = AppError(
        message="Unexpected failure.",
        status_code=418,
        error_code="CUSTOM_ERROR",
    )

    response = handle_app_error(
        build_request(),
        exception,
    )

    assert response.status_code == 418

    body = response.body.decode()

    assert '"success":false' in body
    assert "CUSTOM_ERROR" in body
    assert "Unexpected failure." in body

    mock_logger.exception.assert_called_once_with(
        "Application error occurred",
        extra={
            "error_code": "CUSTOM_ERROR",
            "detail": "Unexpected failure.",
        },
    )


@patch("src.api.exception_handlers.logger")
def test_unhandled_exception_handler(
    mock_logger: MagicMock,
) -> None:
    """
    It should return a generic internal server error response.
    """

    exception = RuntimeError(
        "Boom",
    )

    response = unhandled_exception_handler(
        build_request(),
        exception,
    )

    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    body = response.body.decode()

    assert '"success":false' in body
    assert ERROR_INTERNAL_SERVER_ERROR in body
    assert "Something went wrong on our side." in body

    mock_logger.exception.assert_called_once_with(
        "Unhandled application error",
    )


def test_register_exception_handlers() -> None:
    """
    It should register all exception handlers.
    """

    app = FastAPI()

    app.add_exception_handler = MagicMock()

    register_exception_handlers(
        app,
    )

    assert app.add_exception_handler.call_count == 4

    app.add_exception_handler.assert_any_call(
        DomainError,
        domain_exception_handler,
    )

    app.add_exception_handler.assert_any_call(
        PersistenceError,
        persistence_exception_handler,
    )

    app.add_exception_handler.assert_any_call(
        AppError,
        handle_app_error,
    )

    app.add_exception_handler.assert_any_call(
        Exception,
        unhandled_exception_handler,
    )
