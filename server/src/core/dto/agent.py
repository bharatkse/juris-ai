"""
Agent domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.dto.agent_action import AgentActionRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.response import CitationDTO, SourceDTO, UsageDTO
from core.dto.tool import ToolFileDTO


@dataclass(slots=True, frozen=True)
class AgentContextDTO:
    """
    Runtime context supplied to an agent.
    """

    user_id: str
    execution_id: str
    thread_id: str
    conversation_event_id: str
    uploaded_files: tuple[
        ToolFileDTO,
        ...,
    ] = ()

    # The originating OrchestratorRequest.request_id (as a string),
    # kept separate from thread_id: thread_id identifies the LangGraph
    # checkpoint thread and can differ from the request on a guardrail
    # regenerate attempt (see AIOrchestrator.handle()'s retry loop,
    # which mints a fresh thread_id per attempt) -- request_id must
    # always stay the same real request across every attempt, since
    # it is the correlation key the compliance log
    # (application/services/compliance_log.py) uses to group every row
    # for one turn. Defaults to "" rather than being required so every
    # existing AgentContextDTO() call site (most of them predate this
    # field and don't need it for anything other than compliance
    # logging) keeps working unchanged.
    request_id: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class AgentRequestDTO:
    """
    Request sent to an AI agent.

    The request contains the current ConversationDTO together with
    the runtime context and structured arguments required to execute
    the agent.
    """

    conversation: ConversationDTO
    instruction: str
    context: AgentContextDTO

    arguments: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class AgentResponseDTO:
    """
    Response returned by an AI agent.
    """

    content: str
    agent_name: str
    action: AgentActionRequestDTO | None = None
    citations: tuple[CitationDTO, ...] = ()

    sources: tuple[SourceDTO, ...] = ()
    usage: UsageDTO | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class AgentStreamChunkDTO:
    """
    Streaming response chunk produced by an AI agent.
    """

    content: str = ""

    is_final: bool = False

    finish_reason: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class AgentMetadataDTO:
    """
    Immutable metadata describing an AI agent.
    """

    name: str

    description: str

    capabilities: tuple[
        str,
        ...,
    ]

    tools: tuple[
        str,
        ...,
    ] = ()
