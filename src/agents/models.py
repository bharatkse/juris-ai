"""
Agent domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.clients.models import LLMTokenUsage


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
