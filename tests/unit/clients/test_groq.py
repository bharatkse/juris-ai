"""
Unit tests for GroqClient.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from groq import APIConnectionError, APIStatusError, APITimeoutError

from src.core.config import settings
from src.core.enums import LLMProviderEnum
from src.core.exceptions.client import (
    ClientAuthenticationError,
    ClientError,
    ClientProviderError,
    ClientRateLimitError,
    ClientTimeoutError,
)
from tests.builders.clients.groq import (
    build_groq_chunk_without_delta,
    build_groq_empty_chunk,
    build_groq_messages,
    build_groq_response,
    build_groq_stream,
    build_groq_stream_chunk,
)
from tests.builders.clients.llm import build_llm_request
from tests.unit.clients.exeption_builder import (
    build_authentication_error,
    build_rate_limit_error,
)

TEST_MESSAGES = build_groq_messages()


@pytest.mark.asyncio
async def test_generate_returns_llm_response(
    groq_client,
    mock_chat_completion,
    llm_request,
) -> None:
    """
    It should return an LLM response.
    """

    mock_chat_completion.return_value = build_groq_response()

    response = await groq_client.generate(
        request=llm_request,
    )

    assert response.content == "Hello!"
    assert response.provider == "groq"
    assert response.model == groq_client.model
    assert response.finish_reason == "stop"

    mock_chat_completion.assert_awaited_once_with(
        model=groq_client.model,
        messages=[
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in llm_request.messages
        ],
        temperature=llm_request.temperature,
    )


@pytest.mark.asyncio
async def test_generate_raises_when_content_is_missing(
    groq_client,
    mock_chat_completion,
    llm_request,
) -> None:
    """
    It should raise a provider error when the provider
    returns no content.
    """

    mock_chat_completion.return_value = build_groq_response(
        content=None,
        finish_reason="stop",
        usage=None,
    )

    with pytest.raises(
        ClientProviderError,
        match="returned an empty completion",
    ):
        await groq_client.generate(
            request=llm_request,
        )


@pytest.mark.asyncio
async def test_generate_returns_none_usage_when_provider_does_not_return_usage(
    groq_client, mock_chat_completion, llm_request
) -> None:
    """
    It should return None when token usage is unavailable.
    """

    response = build_groq_response(
        content="Hello",
        finish_reason="stop",
        usage=None,
    )

    mock_chat_completion.return_value = response

    result = await groq_client.generate(
        request=llm_request,
    )

    assert result.usage is None


@pytest.mark.asyncio
async def test_generate_passes_request_parameters(
    groq_client,
    mock_chat_completion,
) -> None:
    """
    It should pass request parameters to the provider.
    """

    request = build_llm_request(
        temperature=0.7,
        max_tokens=500,
    )

    mock_chat_completion.return_value = build_groq_response()

    await groq_client.generate(
        request=request,
    )

    mock_chat_completion.assert_awaited_once_with(
        model=groq_client.model,
        messages=[
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in request.messages
        ],
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_exception", "expected_exception"),
    [
        (
            build_authentication_error(),
            ClientAuthenticationError,
        ),
        (
            build_rate_limit_error(),
            ClientRateLimitError,
        ),
        (
            APITimeoutError(
                "Request timed out",
            ),
            ClientTimeoutError,
        ),
        (
            APIConnectionError(request=MagicMock()),
            ClientError,
        ),
        (
            APIStatusError(
                "Request failed",
                response=MagicMock(),
                body={},
            ),
            ClientError,
        ),
        (
            Exception(
                "Unexpected error",
            ),
            ClientError,
        ),
    ],
)
async def test_generate_translates_provider_exceptions(
    groq_client,
    mock_chat_completion,
    provider_exception,
    expected_exception,
    llm_request,
) -> None:
    """
    It should translate provider exceptions into application exceptions.
    """

    mock_chat_completion.side_effect = provider_exception

    with pytest.raises(expected_exception):
        await groq_client.generate(
            request=llm_request,
        )


@pytest.mark.asyncio
async def test_stream_yields_chunks(groq_client, mock_chat_completion, llm_request) -> None:
    """
    It should yield streamed chunks.
    """

    chunk = build_groq_stream_chunk(content="Hello", finish_reason=None)

    mock_chat_completion.return_value = build_groq_stream(
        chunk,
    )

    chunks = [
        item
        async for item in groq_client.stream(
            request=llm_request,
        )
    ]

    assert len(chunks) == 1
    assert chunks[0].content == "Hello"
    assert chunks[0].is_final is False


@pytest.mark.asyncio
async def test_stream_ignores_empty_choices(groq_client, mock_chat_completion, llm_request) -> None:
    """
    It should ignore chunks without choices.
    """

    chunk = build_groq_empty_chunk()

    mock_chat_completion.return_value = build_groq_stream(
        chunk,
    )

    chunks = [
        item
        async for item in groq_client.stream(
            request=llm_request,
        )
    ]

    assert chunks == []


@pytest.mark.asyncio
async def test_stream_ignores_empty_delta(groq_client, mock_chat_completion, llm_request) -> None:
    """
    It should ignore chunks without a delta.
    """

    chunk = build_groq_chunk_without_delta()

    mock_chat_completion.return_value = build_groq_stream(
        chunk,
    )

    chunks = [
        item
        async for item in groq_client.stream(
            request=llm_request,
        )
    ]

    assert chunks == []


@pytest.mark.asyncio
async def test_stream_ignores_empty_content(groq_client, mock_chat_completion, llm_request) -> None:
    """
    It should ignore chunks without content.
    """

    chunk = build_groq_stream_chunk(finish_reason=None, content="")

    mock_chat_completion.return_value = build_groq_stream(
        chunk,
    )

    chunks = [
        item
        async for item in groq_client.stream(
            request=llm_request,
        )
    ]

    assert len(chunks) == 1
    assert chunks[0].content == ""
    assert chunks[0].is_final is False
    assert chunks[0].finish_reason is None


@pytest.mark.asyncio
async def test_stream_marks_final_chunk(groq_client, mock_chat_completion, llm_request) -> None:
    """
    It should mark the final streamed chunk.
    """

    chunk = build_groq_stream_chunk(finish_reason="stop", content="")

    mock_chat_completion.return_value = build_groq_stream(
        chunk,
    )

    chunks = [
        item
        async for item in groq_client.stream(
            request=llm_request,
        )
    ]

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].finish_reason == "stop"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_exception", "expected_exception"),
    [
        (
            build_authentication_error(),
            ClientAuthenticationError,
        ),
        (
            build_rate_limit_error(),
            ClientRateLimitError,
        ),
        (
            APITimeoutError(
                "Request timed out",
            ),
            ClientTimeoutError,
        ),
        (
            APIConnectionError(request=MagicMock()),
            ClientError,
        ),
        (
            APIStatusError(
                "Request failed",
                response=MagicMock(),
                body={},
            ),
            ClientError,
        ),
        (
            Exception(
                "Unexpected error",
            ),
            ClientError,
        ),
    ],
)
async def test_stream_translates_provider_exceptions(
    groq_client,
    mock_chat_completion,
    provider_exception,
    expected_exception,
    llm_request,
) -> None:
    """
    It should translate provider exceptions while streaming.
    """

    mock_chat_completion.side_effect = provider_exception

    with pytest.raises(expected_exception):
        async for _ in groq_client.stream(
            request=llm_request,
        ):
            pass


def test_provider_returns_provider_name(
    groq_client,
) -> None:
    assert groq_client.provider == LLMProviderEnum.GROQ.value


def test_model_returns_configured_model(
    groq_client,
) -> None:
    assert groq_client.model == settings.GROQ_MODEL


@pytest.mark.asyncio
async def test_stream_yields_multiple_chunks(
    groq_client, mock_chat_completion, llm_request
) -> None:
    """
    It should yield streamed chunks in the order received.
    """

    mock_chat_completion.return_value = build_groq_stream(
        build_groq_stream_chunk(
            content="Hello",
        ),
        build_groq_stream_chunk(
            content=" ",
        ),
        build_groq_stream_chunk(
            content="World",
        ),
        build_groq_stream_chunk(
            content="",
            finish_reason="stop",
        ),
    )

    chunks = [
        chunk
        async for chunk in groq_client.stream(
            request=llm_request,
        )
    ]

    assert len(chunks) == 4

    assert [chunk.content for chunk in chunks] == [
        "Hello",
        " ",
        "World",
        "",
    ]

    assert chunks[0].is_final is False
    assert chunks[1].is_final is False
    assert chunks[2].is_final is False

    assert chunks[-1].is_final is True
    assert chunks[-1].finish_reason == "stop"
