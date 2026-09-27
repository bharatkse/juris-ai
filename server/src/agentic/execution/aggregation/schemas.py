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

    # First-non-None-wins across responses, same convention
    # usage.provider/usage.model below already use for a scalar
    # pulled out of a multi-response sequence -- these are per-
    # response values in AgentResponseDTO.metadata (a free-form dict
    # AgentResponseMapper.map() builds), not naturally summable like
    # token counts. Previously dropped entirely by
    # ResponseAggregator._aggregate_metadata(), so a NEED_INPUT
    # turn's "user_input_required" reason (and a FINAL turn's
    # groundedness/relevance score) never survived aggregation.
    termination_reason: str | None = None

    groundedness: float | None = None

    relevance: float | None = None


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
