"""
Builders for provider-independent LLM models.
"""

from __future__ import annotations

from typing import Any

from src.core.dto.clients.llm import (
    LLMMessageDTO,
    LLMRequestDTO,
    LLMResponseDTO,
    LLMStreamChunkDTO,
    LLMTokenUsageDTO,
)
from src.core.enums import MessageRoleEnum


def build_llm_message(
    *,
    role: MessageRoleEnum = MessageRoleEnum.USER,
    content: str = "Hello",
) -> LLMMessageDTO:
    """
    Build an LLM message.
    """

    return LLMMessageDTO(
        role=role,
        content=content,
    )


def build_llm_messages() -> list[LLMMessageDTO]:
    """
    Build a simple LLM conversation.
    """

    return [
        build_llm_message(
            role=MessageRoleEnum.SYSTEM,
            content="You are a helpful assistant.",
        ),
        build_llm_message(
            role=MessageRoleEnum.USER,
            content="Hello",
        ),
    ]


def build_llm_request(
    *,
    messages: tuple[LLMMessageDTO, ...] | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    metadata: dict[str, object] | None = None,
) -> LLMRequestDTO:
    """
    Build an LLM request.
    """

    return LLMRequestDTO(
        messages=messages
        or tuple(
            build_llm_messages(),
        ),
        temperature=temperature,
        max_tokens=max_tokens,
        metadata=metadata or {},
    )


def build_llm_token_usage(
    *,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    total_tokens: int = 30,
) -> LLMTokenUsageDTO:
    """
    Build LLM token usage.
    """

    return LLMTokenUsageDTO(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def build_llm_response(
    *,
    content: str = "Hello!",
    provider: str = "groq",
    model: str = "llama-3.3-70b-versatile",
    finish_reason: str | None = "stop",
    usage: LLMTokenUsageDTO | None = None,
    metadata: dict[str, Any] | None = None,
) -> LLMResponseDTO:
    """
    Build an LLM response.
    """

    return LLMResponseDTO(
        content=content,
        provider=provider,
        model=model,
        finish_reason=finish_reason,
        usage=usage or build_llm_token_usage(),
        metadata=metadata or {},
    )


def build_llm_stream_chunk(
    *,
    content: str = "Hello",
    is_final: bool = False,
    finish_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LLMStreamChunkDTO:
    """
    Build an LLM stream chunk.
    """

    return LLMStreamChunkDTO(
        content=content,
        is_final=is_final,
        finish_reason=finish_reason,
        metadata=metadata or {},
    )
