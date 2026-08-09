"""
Unit tests for global exception handlers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from starlette.requests import Request

from src.api.exception_handlers import (
    app_exception_handler,
    register_exception_handlers,
    unhandled_exception_handler,
)
from src.core.constants import (
    ERROR_INTERNAL_SERVER_ERROR,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from src.core.exceptions.base import AppError


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
def test_app_exception_handler(
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

    response = app_exception_handler(
        build_request(),
        exception,
    )

    assert response.status_code == 418

    body = response.body.decode()

    assert '"success":false' in body
    assert "CUSTOM_ERROR" in body
    assert "Unexpected failure." in body

    mock_logger.warning.assert_called_once_with(
        "Application error.",
        extra={
            "error_code": "CUSTOM_ERROR",
            "status_code": 418,
            "message": "Unexpected failure.",
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
    assert "An unexpected error occurred. Please try again later." in body

    mock_logger.exception.assert_called_once_with(
        "Unhandled application exception.",
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

    assert app.add_exception_handler.call_count == 2

    app.add_exception_handler.assert_any_call(
        AppError,
        app_exception_handler,
    )

    app.add_exception_handler.assert_any_call(
        Exception,
        unhandled_exception_handler,
    )
