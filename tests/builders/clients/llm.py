"""
Builders for provider-independent LLM models.
"""

from __future__ import annotations

from typing import Any

from src.clients.models import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMTokenUsage,
)
from src.core.enums import MessageRole


def build_llm_message(
    *,
    role: MessageRole = MessageRole.USER,
    content: str = "Hello",
) -> LLMMessage:
    """
    Build an LLM message.
    """

    return LLMMessage(
        role=role,
        content=content,
    )


def build_llm_messages() -> list[LLMMessage]:
    """
    Build a simple LLM conversation.
    """

    return [
        build_llm_message(
            role=MessageRole.SYSTEM,
            content="You are a helpful assistant.",
        ),
        build_llm_message(
            role=MessageRole.USER,
            content="Hello",
        ),
    ]


def build_llm_request(
    *,
    messages: tuple[LLMMessage, ...] | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    metadata: dict[str, object] | None = None,
) -> LLMRequest:
    """
    Build an LLM request.
    """

    return LLMRequest(
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
) -> LLMTokenUsage:
    """
    Build LLM token usage.
    """

    return LLMTokenUsage(
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
    usage: LLMTokenUsage | None = None,
    metadata: dict[str, Any] | None = None,
) -> LLMResponse:
    """
    Build an LLM response.
    """

    return LLMResponse(
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
) -> LLMStreamChunk:
    """
    Build an LLM stream chunk.
    """

    return LLMStreamChunk(
        content=content,
        is_final=is_final,
        finish_reason=finish_reason,
        metadata=metadata or {},
    )
