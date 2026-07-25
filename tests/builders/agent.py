"""
Builders for agent domain models.
"""

from __future__ import annotations

from src.agents.models import AgentChunk, AgentMessage, AgentRequest, AgentResponse
from src.clients.models import LLMMessage, LLMTokenUsage
from src.core.enums import MessageRole


def build_agent_request(
    *,
    question: str = "Hello",
    history: list[AgentMessage] | None = None,
) -> AgentRequest:
    """
    Build an AgentRequest.
    """

    return AgentRequest(
        question=question,
        history=history or [],
    )


def build_agent_chunk(
    *,
    content: str = "Hello",
    is_final: bool = False,
    finish_reason: str | None = None,
    metadata: dict[str, object] | None = None,
) -> AgentChunk:
    """
    Build an AgentChunk.
    """

    return AgentChunk(
        content=content,
        is_final=is_final,
        finish_reason=finish_reason,
        metadata=metadata,
    )


def build_token_usage(
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


def build_agent_response(
    *,
    content: str = "Hello",
    provider: str = "groq",
    model: str = "llama-3.3-70b-versatile",
    finish_reason: str | None = "stop",
    latency_ms: int = 100,
    usage: LLMTokenUsage = None,
    metadata: dict[str, object] | None = None,
) -> AgentResponse:
    """
    Build an AgentResponse.
    """

    return AgentResponse(
        content=content,
        provider=provider,
        model=model,
        finish_reason=finish_reason,
        latency_ms=latency_ms,
        usage=usage,
        metadata=metadata or {},
    )


def build_chat_history() -> list[LLMMessage]:
    """
    Build a simple conversation history.
    """

    return [
        LLMMessage(
            role=MessageRole.SYSTEM,
            content="You are a legal assistant.",
        ),
        LLMMessage(
            role=MessageRole.USER,
            content="Hello",
        ),
        LLMMessage(
            role=MessageRole.ASSISTANT,
            content="Hi! How can I help?",
        ),
    ]
