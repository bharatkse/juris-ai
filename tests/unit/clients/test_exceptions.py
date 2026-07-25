from unittest.mock import MagicMock

import pytest
from groq import APIConnectionError, APIStatusError, APITimeoutError

from src.clients.exceptions import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from tests.builders.groq import build_groq_messages
from tests.unit.clients.exeption_builder import (
    build_authentication_error,
    build_rate_limit_error,
)

TEST_MESSAGES = build_groq_messages()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "provider_exception",
        "expected_exception",
        "status_code",
        "error_code",
        "default_message",
    ),
    [
        (
            build_authentication_error(),
            LLMAuthenticationError,
            LLMAuthenticationError.status_code,
            LLMAuthenticationError.error_code,
            LLMAuthenticationError.default_message,
        ),
        (
            build_rate_limit_error(),
            LLMRateLimitError,
            LLMRateLimitError.status_code,
            LLMRateLimitError.error_code,
            LLMRateLimitError.default_message,
        ),
        (
            APITimeoutError(
                "Request timed out",
            ),
            LLMTimeoutError,
            LLMTimeoutError.status_code,
            LLMTimeoutError.error_code,
            LLMTimeoutError.default_message,
        ),
        (
            APIConnectionError(request=MagicMock()),
            LLMProviderError,
            LLMProviderError.status_code,
            LLMProviderError.error_code,
            LLMProviderError.default_message,
        ),
        (
            APIStatusError(
                "Request failed",
                response=MagicMock(),
                body={},
            ),
            LLMProviderError,
            LLMProviderError.status_code,
            LLMProviderError.error_code,
            LLMProviderError.default_message,
        ),
        (
            Exception(
                "Unexpected error",
            ),
            LLMProviderError,
            LLMProviderError.status_code,
            LLMProviderError.error_code,
            LLMProviderError.default_message,
        ),
    ],
)
async def test_generate_translates_provider_exceptions(
    groq_client,
    mock_chat_completion,
    provider_exception,
    expected_exception,
    status_code,
    error_code,
    default_message,
) -> None:
    """
    It should translate provider exceptions into application exceptions.
    """

    mock_chat_completion.side_effect = provider_exception

    with pytest.raises(
        expected_exception,
    ) as exc_info:
        await groq_client.generate(
            messages=TEST_MESSAGES,
        )

    error = exc_info.value

    assert isinstance(
        error,
        expected_exception,
    )

    assert error.status_code == status_code
    assert error.error_code == error_code
    assert error.default_message == default_message
    assert str(error)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "provider_exception",
        "expected_exception",
        "status_code",
        "error_code",
        "default_message",
    ),
    [
        (
            build_authentication_error(),
            LLMAuthenticationError,
            LLMAuthenticationError.status_code,
            LLMAuthenticationError.error_code,
            LLMAuthenticationError.default_message,
        ),
        (
            build_rate_limit_error(),
            LLMRateLimitError,
            LLMRateLimitError.status_code,
            LLMRateLimitError.error_code,
            LLMRateLimitError.default_message,
        ),
        (
            APITimeoutError(
                "Request timed out",
            ),
            LLMTimeoutError,
            LLMTimeoutError.status_code,
            LLMTimeoutError.error_code,
            LLMTimeoutError.default_message,
        ),
        (
            APIConnectionError(request=MagicMock()),
            LLMProviderError,
            LLMProviderError.status_code,
            LLMProviderError.error_code,
            LLMProviderError.default_message,
        ),
        (
            APIStatusError(
                "Request failed",
                response=MagicMock(),
                body={},
            ),
            LLMProviderError,
            LLMProviderError.status_code,
            LLMProviderError.error_code,
            LLMProviderError.default_message,
        ),
        (
            Exception(
                "Unexpected error",
            ),
            LLMProviderError,
            LLMProviderError.status_code,
            LLMProviderError.error_code,
            LLMProviderError.default_message,
        ),
    ],
)
async def test_stream_translates_provider_exceptions(
    groq_client,
    mock_chat_completion,
    provider_exception,
    expected_exception,
    status_code,
    error_code,
    default_message,
) -> None:
    """
    It should translate provider exceptions while streaming.
    """

    mock_chat_completion.side_effect = provider_exception

    with pytest.raises(
        expected_exception,
    ) as exc_info:
        async for _ in groq_client.stream(
            messages=TEST_MESSAGES,
        ):
            pass

    error = exc_info.value

    assert isinstance(
        error,
        expected_exception,
    )

    assert error.status_code == status_code
    assert error.error_code == error_code
    assert error.default_message == default_message
    assert str(error)
