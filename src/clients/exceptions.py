"""
LLM client exceptions.
"""

from __future__ import annotations

from http import HTTPStatus

from src.core.exceptions import AppError


class LLMClientError(AppError):
    """
    Base exception for all LLM client errors.
    """

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "LLM_CLIENT_ERROR"
    default_message = "An unexpected error occurred while communicating with the language model."


class LLMAuthenticationError(LLMClientError):
    """
    Failed to authenticate with the LLM provider.
    """

    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "LLM_AUTHENTICATION_ERROR"
    default_message = "Failed to authenticate with the language model provider."


class LLMRateLimitError(LLMClientError):
    """
    LLM provider rate limit exceeded.
    """

    status_code = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "LLM_RATE_LIMIT_EXCEEDED"
    default_message = (
        "The language model provider rate limit has been exceeded. Please try again later."
    )


class LLMTimeoutError(LLMClientError):
    """
    LLM request timed out.
    """

    status_code = HTTPStatus.GATEWAY_TIMEOUT
    error_code = "LLM_TIMEOUT"
    default_message = "The language model provider did not respond in time."


class LLMProviderError(LLMClientError):
    """
    Unexpected error returned by the LLM provider.
    """

    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "LLM_PROVIDER_ERROR"
    default_message = "The language model provider returned an unexpected error."
