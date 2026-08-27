"""
Builders for Groq SDK response objects.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import MagicMock

from core.dto.clients.llm import LLMMessageDTO
from tests.builders.adapters.clients.llm import build_llm_message
from tests.helpers.async_iterator import async_iterator

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def build_groq_usage(
    *,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    total_tokens: int = 30,
) -> MagicMock:
    """
    Build a Groq token usage object.
    """

    usage = MagicMock()

    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens

    return usage


def build_groq_choice(
    *,
    content: str | None = "Hello!",
    finish_reason: str | None = "stop",
) -> MagicMock:
    """
    Build a Groq completion choice.
    """

    choice = MagicMock()

    choice.message.content = content
    choice.finish_reason = finish_reason

    return choice


def build_groq_response(
    *,
    content: str | None = "Hello!",
    finish_reason: str | None = "stop",
    model: str = DEFAULT_MODEL,
    usage: MagicMock | None = None,
    response_id: str = "chatcmpl-test",
) -> MagicMock:
    """
    Build a Groq chat completion response.
    """

    response = MagicMock()

    response.id = response_id
    response.model = model
    response.choices = [
        build_groq_choice(
            content=content,
            finish_reason=finish_reason,
        ),
    ]
    response.usage = usage

    return response


def build_groq_stream_choice(
    *,
    content: str | None = "Hello",
    finish_reason: str | None = None,
) -> MagicMock:
    """
    Build a Groq streaming choice.
    """

    choice = MagicMock()

    choice.delta.content = content
    choice.finish_reason = finish_reason

    return choice


def build_groq_stream_chunk(
    *,
    content: str | None = "Hello",
    finish_reason: str | None = None,
) -> MagicMock:
    """
    Build a Groq streaming chunk.
    """

    chunk = MagicMock()

    chunk.choices = [
        build_groq_stream_choice(
            content=content,
            finish_reason=finish_reason,
        ),
    ]

    return chunk


def build_groq_empty_chunk() -> MagicMock:
    """
    Build a streaming chunk without choices.
    """

    chunk = MagicMock()
    chunk.choices = []

    return chunk


def build_groq_chunk_without_delta() -> MagicMock:
    """
    Build a streaming chunk without a delta.
    """

    chunk = MagicMock()

    choice = MagicMock()
    choice.delta = None

    chunk.choices = [
        choice,
    ]

    return chunk


def build_groq_stream(
    *chunks: MagicMock,
) -> AsyncIterator[MagicMock]:
    """
    Build a Groq streaming response.
    """

    return async_iterator(*chunks)


def build_groq_messages(
    *messages: LLMMessageDTO,
) -> list[LLMMessageDTO]:
    """
    Build LLM messages for Groq tests.
    """

    if messages:
        return list(messages)

    return [
        build_llm_message(),
    ]


def build_groq_chat_messages(
    messages: list[LLMMessageDTO],
) -> list[dict[str, str]]:
    """
    Convert LLM messages to Groq SDK format.
    """

    return [
        {
            "role": message.role.value,
            "content": message.content,
        }
        for message in messages
    ]
