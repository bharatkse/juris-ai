"""
LLM exceptions.

LLM exceptions are raised while communicating with Large Language Model
providers through the LLM Gateway.

These exceptions inherit from ``AIError`` and represent failures that
occur during request execution, response processing, or structured
output generation.

LLM Pipeline:

Agent
    │
    ▼
LLM Gateway
    │
    ▼
LLM Provider
    │
    ▼
Structured Response
"""

from __future__ import annotations

from src.core.constants import (
    ERROR_LLM,
    ERROR_LLM_PROVIDER,
    ERROR_LLM_RESPONSE,
    ERROR_LLM_STRUCTURED_OUTPUT,
    ERROR_LLM_TIMEOUT,
)
from src.core.exceptions.base import AIError


class LLMError(AIError):
    """
    Base exception for LLM failures.
    """

    error_code = ERROR_LLM
    default_message = "LLM operation failed."


class LLMProviderError(LLMError):
    """
    Raised when an LLM provider request fails.

    Examples:
        - Authentication failure
        - Rate limit exceeded
        - Provider unavailable
        - Network failure
    """

    error_code = ERROR_LLM_PROVIDER
    default_message = "LLM provider request failed."


class LLMTimeoutError(LLMError):
    """
    Raised when an LLM request exceeds the configured timeout.

    Examples:
        - Provider timeout
        - Gateway timeout
        - Streaming timeout
    """

    error_code = ERROR_LLM_TIMEOUT
    default_message = "LLM request timed out."


class LLMResponseError(LLMError):
    """
    Raised when an LLM returns an invalid or unexpected response.

    Examples:
        - Empty response
        - Malformed response
        - Missing required fields
    """

    error_code = ERROR_LLM_RESPONSE
    default_message = "Invalid LLM response received."


class LLMStructuredOutputError(LLMError):
    """
    Raised when structured output generation fails.

    Examples:
        - JSON parsing failed
        - Response does not match schema
        - Missing required structured fields
    """

    error_code = ERROR_LLM_STRUCTURED_OUTPUT
    default_message = "Structured LLM output validation failed."
