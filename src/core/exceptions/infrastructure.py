"""
Infrastructure exceptions.

Infrastructure exceptions represent unexpected failures caused by
application infrastructure or external dependencies.

Examples:
    - Database failures
    - Cache failures
    - Object storage failures
    - External service failures
    - Message queue failures
    - Application configuration errors

These exceptions inherit from ``InfrastructureError`` and are translated
to HTTP 5xx responses by the application's global exception handlers.
"""

from __future__ import annotations

from src.core.constants import (
    ERROR_CACHE,
    ERROR_CONFIGURATION,
    ERROR_EXTERNAL_SERVICE,
    ERROR_MESSAGE_QUEUE,
    ERROR_PERSISTENCE,
    ERROR_STORAGE,
)
from src.core.exceptions.base import InfrastructureError


class PersistenceError(InfrastructureError):
    """
    Raised when a persistence operation fails.

    Examples:
        - Database connection failure
        - Transaction rollback
        - Query execution failure
        - Repository operation failure
    """

    error_code = ERROR_PERSISTENCE
    default_message = "Persistence operation failed."


class CacheError(InfrastructureError):
    """
    Raised when a cache operation fails.

    Examples:
        - Redis unavailable
        - Cache timeout
        - Cache serialization failure
        - Cache lookup failure
    """

    error_code = ERROR_CACHE
    default_message = "Cache operation failed."


class StorageError(InfrastructureError):
    """
    Raised when a storage operation fails.

    Examples:
        - S3 upload failure
        - MinIO unavailable
        - File system error
        - Object retrieval failure
    """

    error_code = ERROR_STORAGE
    default_message = "Storage operation failed."


class ExternalServiceError(InfrastructureError):
    """
    Raised when communication with an external service fails.

    Examples:
        - LLM provider unavailable
        - OCR provider failure
        - Email service failure
        - Third-party API timeout
    """

    error_code = ERROR_EXTERNAL_SERVICE
    default_message = "External service request failed."


class MessageQueueError(InfrastructureError):
    """
    Raised when a message queue operation fails.

    Examples:
        - Kafka publish failure
        - RabbitMQ connection failure
        - Celery broker unavailable
        - Task dispatch failure
    """

    error_code = ERROR_MESSAGE_QUEUE
    default_message = "Message queue operation failed."


class ConfigurationError(InfrastructureError):
    """
    Raised when the application configuration is invalid.

    Examples:
        - Missing environment variable
        - Invalid configuration value
        - Unsupported provider configuration
        - Invalid application settings
    """

    error_code = ERROR_CONFIGURATION
    default_message = "Application configuration is invalid."
