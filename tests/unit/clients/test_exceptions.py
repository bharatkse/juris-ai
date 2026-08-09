from unittest.mock import MagicMock

import pytest
from groq import APIConnectionError, APIStatusError, APITimeoutError

from src.core.custom_exceptions.client import (
    ClientAuthenticationError,
    ClientConnectionError,
    ClientProviderError,
    ClientRateLimitError,
    ClientTimeoutError,
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
            ClientAuthenticationError,
            ClientAuthenticationError.status_code,
            ClientAuthenticationError.error_code,
            ClientAuthenticationError.default_message,
        ),
        (
            build_rate_limit_error(),
            ClientRateLimitError,
            ClientRateLimitError.status_code,
            ClientRateLimitError.error_code,
            ClientRateLimitError.default_message,
        ),
        (
            APITimeoutError(
                "Request timed out",
            ),
            ClientTimeoutError,
            ClientTimeoutError.status_code,
            ClientTimeoutError.error_code,
            ClientTimeoutError.default_message,
        ),
        (
            APIConnectionError(request=MagicMock()),
            ClientConnectionError,
            ClientConnectionError.status_code,
            ClientConnectionError.error_code,
            ClientConnectionError.default_message,
        ),
        (
            APIStatusError(
                "Request failed",
                response=MagicMock(),
                body={},
            ),
            ClientProviderError,
            ClientProviderError.status_code,
            ClientProviderError.error_code,
            ClientProviderError.default_message,
        ),
        (
            Exception(
                "Unexpected error",
            ),
            ClientProviderError,
            ClientProviderError.status_code,
            ClientProviderError.error_code,
            ClientProviderError.default_message,
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
    llm_request,
) -> None:
    """
    It should translate provider exceptions into application exceptions.
    """

    mock_chat_completion.side_effect = provider_exception

    with pytest.raises(
        expected_exception,
    ) as exc_info:
        await groq_client.generate(
            request=llm_request,
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
            ClientAuthenticationError,
            ClientAuthenticationError.status_code,
            ClientAuthenticationError.error_code,
            ClientAuthenticationError.default_message,
        ),
        (
            build_rate_limit_error(),
            ClientRateLimitError,
            ClientRateLimitError.status_code,
            ClientRateLimitError.error_code,
            ClientRateLimitError.default_message,
        ),
        (
            APITimeoutError(
                "Request timed out",
            ),
            ClientTimeoutError,
            ClientTimeoutError.status_code,
            ClientTimeoutError.error_code,
            ClientTimeoutError.default_message,
        ),
        (
            APIConnectionError(request=MagicMock()),
            ClientConnectionError,
            ClientConnectionError.status_code,
            ClientConnectionError.error_code,
            ClientConnectionError.default_message,
        ),
        (
            APIStatusError(
                "Request failed",
                response=MagicMock(),
                body={},
            ),
            ClientProviderError,
            ClientProviderError.status_code,
            ClientProviderError.error_code,
            ClientProviderError.default_message,
        ),
        (
            Exception(
                "Unexpected error",
            ),
            ClientProviderError,
            ClientProviderError.status_code,
            ClientProviderError.error_code,
            ClientProviderError.default_message,
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
    llm_request,
) -> None:
    """
    It should translate provider exceptions while streaming.
    """

    mock_chat_completion.side_effect = provider_exception

    with pytest.raises(
        expected_exception,
    ) as exc_info:
        async for _ in groq_client.stream(
            request=llm_request,
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
