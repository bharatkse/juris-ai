"""
Provider-independent LLM models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

from core.dto.inference import LLMInferenceConfig
from core.enums import MessageRoleEnum


@dataclass(slots=True, frozen=True)
class LLMMessageDTO:
    """
    Message exchanged with an LLM provider.
    """

    role: MessageRoleEnum

    content: str


@dataclass(slots=True, frozen=True)
class LLMRequestDTO:
    """
    Provider-independent LLM request.
    """

    messages: tuple[LLMMessageDTO, ...]

    inference: LLMInferenceConfig = field(
        default_factory=LLMInferenceConfig,
    )

    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )

    response_format: dict[str, Any] | None = None

    # A narrower JSON Schema than the structured response model's, for
    # this request only (e.g. an agent decision whose tool name must be
    # one of the agent's own tools). Used only by clients that enforce the
    # schema while decoding (LocalLLMClient: Ollama's format, review
    # A19); other providers get the model's own schema, unchanged. The
    # response is validated into the model class either way.
    response_schema: dict[str, Any] | None = None

    def with_response_format(
        self,
        *,
        response_format: dict[str, Any],
    ) -> LLMRequestDTO:
        """
        Return a copy of the request with a response format.
        """

        return replace(
            self,
            response_format=response_format,
        )


@dataclass(slots=True, frozen=True)
class LLMTokenUsageDTO:
    """
    Token usage reported by an LLM provider.
    """

    prompt_tokens: int

    completion_tokens: int

    total_tokens: int


@dataclass(slots=True, frozen=True)
class LLMResponseDTO:
    """
    Provider-independent LLM response.
    """

    content: str

    provider: str

    model: str

    finish_reason: str | None = None

    usage: LLMTokenUsageDTO | None = None

    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )


@dataclass(slots=True, frozen=True)
class LLMStreamChunkDTO:
    """
    Chunk produced while streaming an LLM response.
    """

    content: str = ""

    is_final: bool = False

    finish_reason: str | None = None

    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )
