"""
Unit tests for ApiResponse.
"""

from __future__ import annotations

from api.utilities.api_response import ApiResponse
from core.models.response import ErrorDetailModel, MetadataModel


def test_api_response_returns_success_response() -> None:
    """
    It should return a successful response.
    """

    response = ApiResponse(
        message="Success",
        data={
            "id": 1,
        },
    )

    assert response.status_code == 200

    body = response.body.decode()

    assert '"success":true' in body
    assert '"message":"Success"' in body
    assert '"data":{"id":1}' in body
    assert '"metadata"' in body
    assert '"error"' not in body


def test_api_response_returns_error_response() -> None:
    """
    It should return an error response.
    """

    error = ErrorDetailModel(
        code="USER_NOT_FOUND",
        message="User not found.",
    )

    response = ApiResponse(
        error=error,
    )

    assert response.status_code == 500

    body = response.body.decode()

    assert '"success":false' in body
    assert '"error"' in body
    assert '"USER_NOT_FOUND"' in body
    assert '"data"' not in body


def test_api_response_uses_custom_status_code() -> None:
    """
    It should use the provided status code.
    """

    response = ApiResponse(
        status_code=201,
        data={
            "id": 1,
        },
    )

    assert response.status_code == 201


def test_api_response_uses_custom_headers() -> None:
    """
    It should include custom headers.
    """

    response = ApiResponse(
        headers={
            "X-Request-Id": "request_123",
        },
    )

    assert response.headers["X-Request-Id"] == "request_123"


def test_api_response_uses_provided_metadata() -> None:
    """
    It should use the provided metadata.
    """

    metadata = MetadataModel(
        request_id="request_123",
        trace_id="trace_123",
    )

    response = ApiResponse(
        data={
            "id": 1,
        },
        metadata=metadata,
    )

    body = response.body.decode()

    assert '"request_id":"request_123"' in body
    assert '"trace_id":"trace_123"' in body


def test_api_response_creates_default_metadata() -> None:
    """
    It should create metadata when none is provided.
    """

    response = ApiResponse(
        data={
            "id": 1,
        },
    )

    body = response.body.decode()

    assert '"metadata"' in body
    assert '"timestamp"' in body


def test_api_response_ignores_success_parameter_when_error_exists() -> None:
    """
    It should derive success from the presence of an error.
    """

    error = ErrorDetailModel(
        code="ERROR",
        message="Failure",
    )

    response = ApiResponse(
        success=True,
        error=error,
    )

    body = response.body.decode()

    assert response.status_code == 500
    assert '"success":false' in body


def test_api_response_ignores_success_parameter_without_error() -> None:
    """
    It should derive success from the absence of an error.
    """

    response = ApiResponse(
        success=False,
        message="Success",
    )

    body = response.body.decode()

    assert response.status_code == 200
    assert '"success":true' in body


def test_api_response_excludes_none_fields() -> None:
    """
    It should exclude fields with None values.
    """

    response = ApiResponse()

    body = response.body.decode()

    assert '"success":true' in body
    assert '"metadata"' in body
    assert '"message"' not in body
    assert '"data"' not in body
    assert '"error"' not in body


def test_api_response_uses_custom_error_status_code() -> None:
    """
    It should use the provided status code for an error response.
    """

    error = ErrorDetailModel(
        code="FORBIDDEN",
        message="Forbidden.",
    )

    response = ApiResponse(
        error=error,
        status_code=403,
    )

    assert response.status_code == 403

    body = response.body.decode()

    assert '"success":false' in body
    assert '"FORBIDDEN"' in body
