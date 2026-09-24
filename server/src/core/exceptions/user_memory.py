"""
User memory exceptions.
"""

from __future__ import annotations

from core.exceptions.domain import ConflictError, DomainValidationError


class InvalidUserMemoryContentError(DomainValidationError):
    """
    Raised when proposed memory content is empty or too long to be a
    single atomic fact.
    """

    default_message = "Memory content is not a valid single fact."


class UserMemoryLimitExceededError(ConflictError):
    """
    Raised when a user already holds the maximum number of memories.
    """

    default_message = "Memory limit reached."
