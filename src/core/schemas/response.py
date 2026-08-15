"""
Shared request and response schemas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class PaginationParams(BaseModel):
    """
    Query parameters for paginated endpoints.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    offset: int = Field(
        default=0,
        ge=0,
        description="Number of records to skip.",
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of records to return.",
    )


class PaginationModel(BaseModel):
    """
    Pagination metadata.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    total: int

    offset: int

    limit: int

    has_more: bool


class Page(BaseModel, Generic[DataT]):
    """
    Generic paginated payload.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    items: list[DataT]

    pagination: PaginationModel


class AIUsageModel(BaseModel):
    """
    AI execution information.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    provider: str | None = None

    model: str | None = None

    agent: str | None = None

    workflow: str | None = None

    latency_ms: int | None = None

    prompt_tokens: int | None = None

    completion_tokens: int | None = None

    total_tokens: int | None = None

    tool_calls: int | None = None


class MetadataModel(BaseModel):
    """
    Response metadata.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    request_id: str | None = None

    trace_id: str | None = None

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    ai: AIUsageModel | None = None


class ErrorDetailModel(BaseModel):
    """
    Standard API error.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    code: str

    message: str

    details: dict[str, Any] | None = None


class ApiResponseModel(BaseModel, Generic[DataT]):
    """
    Standard API response envelope.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    success: bool

    data: DataT | None = None

    error: ErrorDetailModel | None = None

    metadata: MetadataModel

    message: str | None = None
