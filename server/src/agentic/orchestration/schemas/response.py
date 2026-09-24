"""
Outgoing response models.

These models represent the final response produced by the AI
orchestrator after planning, execution, validation, and aggregation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentic.guardrails.schemas import GuardrailActionEnum
from core.dto.agent_action import AgentActionRequestDTO
from core.enums import ApprovalStatusEnum
from core.types import ConversationId


class Citation(BaseModel):
    """
    Citation supporting the generated response.

    from_attributes=True: ResponseAggregator._aggregate_citations()
    passes core.dto.response.CitationDTO instances (a frozen dataclass,
    field-for-field identical to this model) straight through into
    AggregatedResponse.citations: list[Citation] -- without this,
    pydantic rejects a dataclass instance outright wherever a
    BaseModel is declared, since it's neither a dict nor an instance
    of this exact class. Confirmed live: this made every FINAL answer
    carrying a non-empty citation fail at the aggregation boundary --
    caught while verifying the HITL resume path end-to-end, since that
    was the first thing to actually drive a real citation through this
    exact construction (see claude.md's HITL trace).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    title: str

    source: str

    reference: str | None = None

    page: int | None = None

    snippet: str | None = None


class Source(BaseModel):
    """
    Source used to generate the response.

    from_attributes=True: see Citation's docstring above -- same
    reason, same fix, for core.dto.response.SourceDTO.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    title: str

    uri: str | None = None

    type: str | None = None


class Usage(BaseModel):
    """
    LLM usage information.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    provider: str | None = None

    model: str | None = None

    prompt_tokens: int = 0

    completion_tokens: int = 0

    total_tokens: int = 0

    latency_ms: float | None = None


class ResponseMetadata(BaseModel):
    """
    Execution metadata.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    agents: list[str] = Field(
        default_factory=list,
    )

    workflow: str | None = None

    termination_reason: str | None = None

    groundedness: float | None = None

    relevance: float | None = None


class ResponsePayload(BaseModel):
    """
    Common response payload.
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

    usage: Usage = Field(
        default_factory=Usage,
    )

    metadata: ResponseMetadata = Field(
        default_factory=ResponseMetadata,
    )


class AgentResponse(ResponsePayload):
    """
    Response produced by a single agent.
    """

    agent_name: str


class GuardrailInfo(BaseModel):
    """
    What the output guardrail did to this response, if anything.

    Deliberately carries only the action taken plus counts/categories
    -- never the matched PII text itself (see agentic.guardrails'
    no-raw-content-in-detections design) -- since this is what gets
    persisted into assistant_event.metadata (ChatService) and, later,
    the compliance log.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    action: GuardrailActionEnum
    detection_count: int = 0
    categories: list[str] = Field(
        default_factory=list,
    )
    harmful: bool = False
    harmful_category: str | None = None


class ApprovalResponse(BaseModel):
    """
    Human approval information returned by the orchestrator.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    approval_id: str
    status: ApprovalStatusEnum
    expires_at: datetime


class OrchestratorResponse(ResponsePayload):
    """
    Final response returned by the AI orchestrator.
    """

    conversation_id: ConversationId
    approval: ApprovalResponse | None = None
    action: AgentActionRequestDTO | None = None
    guardrail: GuardrailInfo | None = None


class OrchestratorStreamChunk(BaseModel):
    """
    Chunk yielded while streaming a chat response
    (AIOrchestrator.stream()).

    The final chunk (is_final=True) carries the complete
    OrchestratorResponse -- the same object handle() would return for
    the same inputs, built the same way (see stream()'s docstring).
    Intermediate chunks carry only display content.

    Defined here, not in application/services/internal_dto/stream.py
    (where the field-identical ChatStreamChunkDTO used to live as its
    own class): AIOrchestrator (agentic/) is what actually constructs
    this, and agentic/ must never import from application/ -- the
    reverse of this project's layering (application/ already depends
    on agentic/, e.g. ChatService imports AIOrchestrator directly).
    ChatStreamChunkDTO is now a plain alias for this class instead of
    a separate, field-duplicating one -- see that module's comment.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    content: str = ""
    is_final: bool = False
    response: OrchestratorResponse | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )
