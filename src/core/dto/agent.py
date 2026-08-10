"""
Agent domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.dto.conversation import ConversationDTO
from src.core.dto.response import CitationDTO, SourceDTO, UsageDTO
from src.core.dto.tool import ToolFileDTO


@dataclass(slots=True, frozen=True)
class AgentContextDTO:
    """
    Runtime context supplied to an agent.
    """

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
    the runtime context required to execute the agent.
    """

    conversation: ConversationDTO
    instruction: str
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
