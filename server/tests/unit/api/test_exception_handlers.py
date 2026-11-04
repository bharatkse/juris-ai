"""
Unit tests for global exception handlers.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from starlette.requests import Request

from api.exception_handlers import (
    GENERIC_ERROR_MESSAGE,
    app_exception_handler,
    public_error,
    register_exception_handlers,
    unhandled_exception_handler,
)
from core.constants import ERROR_INTERNAL_SERVER_ERROR, HTTP_500_INTERNAL_SERVER_ERROR
from core.exceptions.base import AppError
from core.exceptions.client import ClientProviderError
from core.exceptions.planning import PlanningUnavailableError


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


@patch("api.exception_handlers.logger")
def test_app_exception_handler_returns_the_errors_details(
    mock_logger: MagicMock,
) -> None:
    """
    Structured details on an application error reach the response body.
    """

    exception = AppError(
        message="Already decided.",
        status_code=409,
        error_code="CUSTOM_CONFLICT",
        details={"current_status": "approved"},
    )

    response = app_exception_handler(build_request(), exception)

    assert '"details":{"current_status":"approved"}' in response.body.decode()


@patch("api.exception_handlers.logger")
def test_app_exception_handler_sends_the_errors_headers(
    mock_logger: MagicMock,
) -> None:
    """
    Headers an application error carries (e.g. Retry-After) are sent.
    """

    exception = AppError(
        message="Try again shortly.",
        status_code=503,
        error_code="CUSTOM_UNAVAILABLE",
        headers={"Retry-After": "30"},
    )

    response = app_exception_handler(build_request(), exception)

    assert response.status_code == 503
    assert response.headers["retry-after"] == "30"


@patch("api.exception_handlers.logger")
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
            "error_message": "Unexpected failure.",
        },
    )


@patch("api.exception_handlers.logger")
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


# ---------------------------------------------------------------------------
# What a client sees (Phase 4, P4-EL): a server error never carries the
# exception's own text or details, only its code, a generic message and the
# request ID to quote; errors meant for the client keep their message.
# ---------------------------------------------------------------------------

REQUEST_ID = "4f1c0b8e-2d5a-4c1e-9a7b-3e6d2f1a0b9c"
INTERNAL_TEXT = "OperationalError: password authentication failed for user app_rw"


def build_request_with_id() -> Request:
    request = build_request()
    request.state.context = SimpleNamespace(request_id=REQUEST_ID)
    return request


def body_of(response) -> dict:
    return json.loads(response.body.decode())


@patch("api.exception_handlers.logger")
def test_a_server_error_hides_its_text_and_details(mock_logger: MagicMock) -> None:
    exception = AppError(
        message=INTERNAL_TEXT,
        status_code=500,
        error_code="PERSISTENCE_ERROR",
        details={"statement": "insert into conversation_events ..."},
    )

    response = app_exception_handler(build_request_with_id(), exception)

    body = body_of(response)
    assert response.status_code == 500
    assert body["error"] == {
        "code": "PERSISTENCE_ERROR",
        "message": GENERIC_ERROR_MESSAGE,
        "request_id": REQUEST_ID,
    }
    assert body["metadata"]["request_id"] == REQUEST_ID
    assert response.headers["x-request-id"] == REQUEST_ID
    assert "password" not in response.body.decode()


@patch("api.exception_handlers.logger")
def test_a_provider_error_hides_the_providers_text(mock_logger: MagicMock) -> None:
    exception = ClientProviderError("Upstream said: invalid api key gsk_live_123 for org-9")

    response = app_exception_handler(build_request_with_id(), exception)

    body = body_of(response)
    assert response.status_code == 502
    assert body["error"]["code"] == "CLIENT_PROVIDER_ERROR"
    assert body["error"]["message"] == GENERIC_ERROR_MESSAGE
    assert "gsk_live" not in response.body.decode()


@patch("api.exception_handlers.logger")
def test_a_server_error_meant_for_the_client_keeps_its_message(
    mock_logger: MagicMock,
) -> None:
    exception = PlanningUnavailableError(retry_after_seconds=30)

    response = app_exception_handler(build_request_with_id(), exception)

    body = body_of(response)
    assert response.status_code == 503
    assert body["error"]["message"] == exception.message
    assert body["error"]["details"] == {"retry_after_seconds": 30}
    assert body["error"]["request_id"] == REQUEST_ID
    assert response.headers["retry-after"] == "30"


@patch("api.exception_handlers.logger")
def test_a_client_error_keeps_its_message_and_details_and_gets_the_request_id(
    mock_logger: MagicMock,
) -> None:
    exception = AppError(
        message="Already decided.",
        status_code=409,
        error_code="APPROVAL_ALREADY_DECIDED",
        details={"current_status": "approved"},
    )

    response = app_exception_handler(build_request_with_id(), exception)

    body = body_of(response)
    assert body["error"] == {
        "code": "APPROVAL_ALREADY_DECIDED",
        "message": "Already decided.",
        "details": {"current_status": "approved"},
        "request_id": REQUEST_ID,
    }
    assert response.headers["x-request-id"] == REQUEST_ID


@patch("api.exception_handlers.logger")
def test_an_unhandled_exception_carries_the_request_id_not_its_text(
    mock_logger: MagicMock,
) -> None:
    response = unhandled_exception_handler(build_request_with_id(), RuntimeError(INTERNAL_TEXT))

    body = body_of(response)
    assert body["error"] == {
        "code": ERROR_INTERNAL_SERVER_ERROR,
        "message": GENERIC_ERROR_MESSAGE,
        "request_id": REQUEST_ID,
    }
    assert response.headers["x-request-id"] == REQUEST_ID
    assert "password" not in response.body.decode()


@patch("api.exception_handlers.logger")
def test_a_request_without_context_still_gets_a_generic_error(mock_logger: MagicMock) -> None:
    response = unhandled_exception_handler(build_request(), RuntimeError(INTERNAL_TEXT))

    body = body_of(response)
    assert body["error"] == {"code": ERROR_INTERNAL_SERVER_ERROR, "message": GENERIC_ERROR_MESSAGE}
    assert "x-request-id" not in response.headers


def test_public_error_is_shared_by_http_and_the_stream() -> None:
    error = public_error(ClientProviderError(INTERNAL_TEXT), request_id=REQUEST_ID)

    assert error.model_dump(exclude_none=True) == {
        "code": "CLIENT_PROVIDER_ERROR",
        "message": GENERIC_ERROR_MESSAGE,
        "request_id": REQUEST_ID,
    }
