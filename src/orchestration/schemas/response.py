"""
Outgoing response models.

These models represent the final response produced by the AI
orchestrator after planning, execution, validation, and aggregation.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import ApprovalStatusEnum
from src.core.types import ConversationId


class Citation(BaseModel):
    """
    Citation supporting the generated response.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    title: str

    source: str

    reference: str | None = None

    page: int | None = None

    snippet: str | None = None


class Source(BaseModel):
    """
    Source used to generate the response.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
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
