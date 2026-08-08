"""
Agent domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.models.conversation import Conversation
from src.core.models.tool import ToolFile


@dataclass(slots=True, frozen=True)
class AgentContext:
    """
    Runtime context supplied to an agent.
    """

    uploaded_files: tuple[
        ToolFile,
        ...,
    ] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class AgentRequest:
    """
    Request sent to an AI agent.

    The request contains the current conversation together with
    the runtime context required to execute the agent.
    """

    conversation: Conversation

    context: AgentContext = field(
        default_factory=AgentContext,
    )


@dataclass(slots=True, frozen=True)
class AgentResponse:
    """
    Response returned by an AI agent.
    """

    content: str

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class AgentStreamChunk:
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
class AgentMetadata:
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
