"""
Provider-independent LLM models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from src.core.enums import MessageRole


@dataclass(slots=True, frozen=True)
class LLMMessage:
    """
    Message exchanged with an LLM provider.
    """

    role: MessageRole

    content: str


@dataclass(slots=True, frozen=True)
class LLMRequest:
    """
    Provider-independent LLM request.
    """

    messages: tuple[LLMMessage, ...]

    temperature: float = 0.2

    max_tokens: int | None = None

    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )


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

    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )


@dataclass(slots=True, frozen=True)
class LLMStreamChunk:
    """
    Chunk produced while streaming an LLM response.
    """

    content: str = ""

    is_final: bool = False

    finish_reason: str | None = None

    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )
