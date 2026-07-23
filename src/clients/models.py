"""
Provider-independent LLM models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.enums import MessageRole


@dataclass(slots=True, frozen=True)
class LLMMessage:
    """
    Message sent to an LLM.
    """

    role: MessageRole

    content: str


@dataclass(slots=True, frozen=True)
class LLMTokenUsage:
    """
    Token usage reported by an LLM provider.
    """

    prompt_tokens: int

    completion_tokens: int

    total_tokens: int


@dataclass(slots=True, frozen=True)
class LLMResponse:
    """
    Provider-independent LLM response.
    """

    content: str

    provider: str

    model: str

    finish_reason: str | None = None

    usage: LLMTokenUsage | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
