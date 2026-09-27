"""
Validation exceptions.
"""

from __future__ import annotations

from core.constants import HTTP_422_UNPROCESSABLE_ENTITY
from core.exceptions.base import DomainError


class ValidationError(DomainError):
    """
    Raised when one or more agent responses fail validation.
    """

    status_code = HTTP_422_UNPROCESSABLE_ENTITY

    error_code = "VALIDATION_ERROR"


class EmptyResponseError(ValidationError):
    """
    Raised when no responses are available for validation.
    """

    error_code = "EMPTY_RESPONSE"

    def __init__(
        self,
        message: str = "No responses were produced.",
    ) -> None:
        super().__init__(message)


class EmptyContentError(ValidationError):
    """
    Raised when a response contains no content.
    """

    error_code = "EMPTY_CONTENT"

    def __init__(
        self,
        *,
        agent_name: str,
    ) -> None:
        super().__init__(
            f"Agent '{agent_name}' returned empty content.",
        )


class DuplicateAgentResponseError(ValidationError):
    """
    Raised when multiple responses are returned from the same agent.
    """

    error_code = "DUPLICATE_AGENT_RESPONSE"

    def __init__(
        self,
        *,
        agent_name: str,
    ) -> None:
        super().__init__(
            f"Duplicate response received from agent '{agent_name}'.",
        )
