"""
Builders for LLM domain models.
"""

from __future__ import annotations

from src.clients.models import LLMMessage, LLMResponse, LLMStreamChunk, LLMTokenUsage
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
    Build a simple conversation.
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


def build_llm_token_usage(
    *,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    total_tokens: int = 30,
) -> LLMTokenUsage:
    """
    Build token usage.
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
    finish_reason: str = "stop",
    usage: LLMTokenUsage | None = None,
    metadata: dict | None = None,
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
        metadata=metadata,
    )


def build_llm_chunk(
    *,
    content: str = "Hello",
    is_final: bool = False,
    finish_reason: str | None = None,
    metadata: dict | None = None,
) -> LLMStreamChunk:
    """
    Build a streamed LLM chunk.
    """

    return LLMStreamChunk(
        content=content,
        is_final=is_final,
        finish_reason=finish_reason,
        metadata=metadata,
    )
