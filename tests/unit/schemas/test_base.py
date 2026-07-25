"""
Unit tests for shared schemas.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.schemas.base import (
    AIInfoModel,
    ApiResponseModel,
    ErrorDetailModel,
    ListData,
    MetadataModel,
    Pagination,
    PaginationParams,
)


def test_pagination_params_uses_defaults() -> None:
    """
    It should use the default pagination values.
    """

    params = PaginationParams()

    assert params.skip == 0
    assert params.limit == 10


def test_pagination_params_accepts_custom_values() -> None:
    """
    It should accept custom pagination values.
    """

    params = PaginationParams(
        skip=20,
        limit=50,
    )

    assert params.skip == 20
    assert params.limit == 50


def test_pagination_params_rejects_negative_skip() -> None:
    """
    It should reject a negative skip value.
    """

    with pytest.raises(
        ValidationError,
    ):
        PaginationParams(
            skip=-1,
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


def test_pagination_accepts_valid_values() -> None:
    """
    It should accept pagination information.
    """

    pagination = Pagination(
        total=100,
        skip=10,
        limit=20,
        has_more=True,
    )

    assert pagination.total == 100
    assert pagination.skip == 10
    assert pagination.limit == 20
    assert pagination.has_more is True


def test_pagination_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        Pagination(
            total=1,
            skip=0,
            limit=10,
            has_more=False,
            unknown="value",
        )


def test_list_data_accepts_items() -> None:
    """
    It should store a paginated list.
    """

    pagination = Pagination(
        total=2,
        skip=0,
        limit=10,
        has_more=False,
    )

    data = ListData[str](
        items=[
            "A",
            "B",
        ],
        pagination=pagination,
    )

    assert data.items == [
        "A",
        "B",
    ]

    assert data.pagination is pagination


def test_ai_info_model_accepts_values() -> None:
    """
    It should store AI execution metadata.
    """

    info = AIInfoModel(
        provider="groq",
        model="llama-3",
        latency_ms=120,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        tool_calls=2,
    )

    assert info.provider == "groq"
    assert info.model == "llama-3"
    assert info.total_tokens == 30


def test_ai_info_model_uses_defaults() -> None:
    """
    It should default all fields to None.
    """

    info = AIInfoModel()

    assert info.provider is None
    assert info.model is None
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

    ai = AIInfoModel(
        provider="groq",
    )

    metadata = MetadataModel(
        request_id="req_123",
        ai=ai,
    )

    assert metadata.request_id == "req_123"
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
    )

    assert response.success is False
    assert response.data is None
    assert response.error is error


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
