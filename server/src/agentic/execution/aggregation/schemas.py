"""
Aggregation models.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic.orchestration.schemas.response import Citation, Source, Usage


class AggregationMetadata(BaseModel):
    """
    Metadata produced during response aggregation.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    agents: list[str] = Field(
        default_factory=list,
    )

    merged_responses: int = 0

    usage: Usage = Field(
        default_factory=Usage,
    )


class AggregatedResponse(BaseModel):
    """
    Final aggregated response.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    content: str

    citations: list[Citation] = Field(
        default_factory=list,
    )

    sources: list[Source] = Field(
        default_factory=list,
    )

    metadata: AggregationMetadata = Field(
        default_factory=AggregationMetadata,
    )


class AggregationResult(BaseModel):
    """
    Result of aggregating multiple agent responses.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    response: AggregatedResponse

    warnings: list[str] = Field(
        default_factory=list,
    )
