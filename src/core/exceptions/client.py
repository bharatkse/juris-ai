"""
Client exceptions.
"""

from __future__ import annotations

from http import HTTPStatus

from core.exceptions.base import AppError


class ClientError(AppError):
    """
    Base exception for external client failures.
    """

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "CLIENT_ERROR"
    default_message = "An unexpected error occurred while communicating with an external service."


class ClientConfigurationError(ClientError):
    """
    Client configuration is invalid.
    """

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "CLIENT_CONFIGURATION_ERROR"
    default_message = "The external client is not configured correctly."


class ClientAuthenticationError(ClientError):
    """
    Authentication with the external service failed.
    """

    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "CLIENT_AUTHENTICATION_ERROR"
    default_message = "Failed to authenticate with the external service."


class ClientAuthorizationError(ClientError):
    """
    Authorization was denied by the external service.
    """

    status_code = HTTPStatus.FORBIDDEN
    error_code = "CLIENT_AUTHORIZATION_ERROR"
    default_message = "The external service denied the request."


class ClientRateLimitError(ClientError):
    """
    The external service rate limit has been exceeded.
    """

    status_code = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "CLIENT_RATE_LIMIT_ERROR"
    default_message = "The external service rate limit has been exceeded."


class ClientTimeoutError(ClientError):
    """
    The external service did not respond in time.
    """

    status_code = HTTPStatus.GATEWAY_TIMEOUT
    error_code = "CLIENT_TIMEOUT"
    default_message = "The external service did not respond in time."


class ClientConnectionError(ClientError):
    """
    Unable to establish a connection to the external service.
    """

    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "CLIENT_CONNECTION_ERROR"
    default_message = "Unable to connect to the external service."


class ClientResponseError(ClientError):
    """
    The external service returned an invalid response.
    """

    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "CLIENT_RESPONSE_ERROR"
    default_message = "The external service returned an invalid response."


class ClientProviderError(ClientError):
    """
    The external service returned an unexpected error.
    """

    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "CLIENT_PROVIDER_ERROR"
    default_message = "The external service returned an unexpected error."
