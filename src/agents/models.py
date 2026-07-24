"""
Agent domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.clients.models import LLMTokenUsage
from src.core.enums import MessageRole


@dataclass(slots=True, frozen=True)
class AgentResponse:
    """
    Response returned by an AI agent.

    This is the contract between the Agent layer and the
    Service layer. It is intentionally independent of any
    specific LLM provider.
    """

    content: str

    provider: str

    model: str

    finish_reason: str | None = None

    latency_ms: int | None = None

    usage: LLMTokenUsage | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class AgentChunk:
    """
    Streamed chunk produced by an AI agent.
    """

    content: str = ""

    is_final: bool = False

    finish_reason: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class AgentMessage:
    """
    Conversation message understood by the Agent layer.
    """

    role: MessageRole

    content: str


@dataclass(slots=True, frozen=True)
class AgentRequest:
    """
    Request sent to an AI agent.
    """

    question: str

    history: list[AgentMessage] = field(
        default_factory=list,
    )
