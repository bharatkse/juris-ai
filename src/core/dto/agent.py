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

    arguments: dict[str, Any] = field(
        default_factory=dict,
    )

    context: AgentContextDTO = field(
        default_factory=AgentContextDTO,
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
