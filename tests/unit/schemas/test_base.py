"""
Unit tests for shared schemas.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.core.schemas.response import (
    AIUsageModel,
    ApiResponseModel,
    ErrorDetailModel,
    MetadataModel,
    Page,
    PaginationModel,
    PaginationParams,
)


def test_pagination_params_uses_defaults() -> None:
    """
    It should use the default pagination values.
    """

    params = PaginationParams()

    assert params.offset == 0
    assert params.limit == 20


def test_pagination_params_accepts_custom_values() -> None:
    """
    It should accept custom pagination values.
    """

    params = PaginationParams(
        offset=20,
        limit=50,
    )

    assert params.offset == 20
    assert params.limit == 50


def test_pagination_params_rejects_negative_offset() -> None:
    """
    It should reject a negative offset value.
    """

    with pytest.raises(
        ValidationError,
    ):
        PaginationParams(
            offset=-1,
        )


def test_pagination_params_rejects_limit_less_than_one() -> None:
    """
    It should reject a limit less than one.
    """

    with pytest.raises(
        ValidationError,
    ):
        PaginationParams(
            limit=0,
        )


def test_pagination_params_rejects_limit_greater_than_maximum() -> None:
    """
    It should reject a limit greater than the maximum.
    """

    with pytest.raises(
        ValidationError,
    ):
        PaginationParams(
            limit=101,
        )


def test_pagination_params_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        PaginationParams(
            unknown="value",
        )


def test_pagination_model_accepts_valid_values() -> None:
    """
    It should accept pagination information.
    """

    pagination = PaginationModel(
        total=100,
        offset=10,
        limit=20,
        has_more=True,
    )

    assert pagination.total == 100
    assert pagination.offset == 10
    assert pagination.limit == 20
    assert pagination.has_more is True


def test_pagination_model_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        PaginationModel(
            total=1,
            offset=0,
            limit=10,
            has_more=False,
            unknown="value",
        )


def test_page_accepts_items() -> None:
    """
    It should accept paginated items.
    """

    page = Page[str](
        items=[
            "a",
            "b",
        ],
        pagination=PaginationModel(
            total=2,
            offset=0,
            limit=20,
            has_more=False,
        ),
    )

    assert page.items == [
        "a",
        "b",
    ]
    assert page.pagination.total == 2


def test_ai_usage_model_accepts_values() -> None:
    """
    It should store AI execution metadata.
    """

    info = AIUsageModel(
        provider="groq",
        model="llama-3",
        agent="legal",
        workflow="qa",
        latency_ms=120,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        tool_calls=2,
    )

    assert info.provider == "groq"
    assert info.model == "llama-3"
    assert info.agent == "legal"
    assert info.workflow == "qa"
    assert info.total_tokens == 30


def test_ai_usage_model_uses_defaults() -> None:
    """
    It should default all fields to None.
    """

    info = AIUsageModel()

    assert info.provider is None
    assert info.model is None
    assert info.agent is None
    assert info.workflow is None
    assert info.total_tokens is None


def test_metadata_model_uses_current_timestamp() -> None:
    """
    It should generate a timestamp automatically.
    """

    metadata = MetadataModel()

    assert isinstance(
        metadata.timestamp,
        datetime,
    )

    assert metadata.timestamp.tzinfo == UTC


def test_metadata_model_accepts_ai_metadata() -> None:
    """
    It should store AI metadata.
    """

    ai = AIUsageModel(
        provider="groq",
    )

    metadata = MetadataModel(
        request_id="req_123",
        trace_id="trace_123",
        ai=ai,
    )

    assert metadata.request_id == "req_123"
    assert metadata.trace_id == "trace_123"
    assert metadata.ai is ai


def test_error_detail_model_accepts_values() -> None:
    """
    It should store error details.
    """

    error = ErrorDetailModel(
        code="NOT_FOUND",
        message="User not found.",
        details={
            "user_id": "123",
        },
    )

    assert error.code == "NOT_FOUND"
    assert error.message == "User not found."
    assert error.details == {
        "user_id": "123",
    }


def test_api_response_model_accepts_success_response() -> None:
    """
    It should store a successful response.
    """

    response = ApiResponseModel[str](
        success=True,
        data="Hello",
        metadata=MetadataModel(),
    )

    assert response.success is True
    assert response.data == "Hello"
    assert response.error is None
    assert response.message is None


def test_api_response_model_accepts_error_response() -> None:
    """
    It should store an error response.
    """

    error = ErrorDetailModel(
        code="NOT_FOUND",
        message="User not found.",
    )

    response = ApiResponseModel[None](
        success=False,
        error=error,
        metadata=MetadataModel(),
        message="Failed",
    )

    assert response.success is False
    assert response.data is None
    assert response.error is error
    assert response.message == "Failed"


def test_api_response_model_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        ApiResponseModel(
            success=True,
            metadata=MetadataModel(),
            unknown="value",
        )
