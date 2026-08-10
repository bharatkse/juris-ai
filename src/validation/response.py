"""
Response validator.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.core.exceptions.validation import (
    DuplicateAgentResponseError,
    EmptyContentError,
    EmptyResponseError,
)
from src.orchestration.response import AgentResponse
from src.validation.base import BaseValidator


class ResponseValidator(BaseValidator):
    """
    Validates responses produced by one or more agents.
    """

    async def validate(
        self,
        *,
        responses: Sequence[AgentResponse],
    ) -> None:
        """
        Validate agent responses.

        Raises:
            ValidationError
        """

        if not responses:
            raise EmptyResponseError()

        self._validate_unique_agents(
            responses,
        )

        self._validate_content(
            responses,
        )

    @staticmethod
    def _validate_unique_agents(
        responses: Sequence[AgentResponse],
    ) -> None:
        """
        Ensure each agent contributes at most one response.
        """

        seen: set[str] = set()

        for response in responses:
            if response.agent_name in seen:
                raise DuplicateAgentResponseError(
                    agent_name=response.agent_name,
                )

            seen.add(
                response.agent_name,
            )

    @staticmethod
    def _validate_content(
        responses: Sequence[AgentResponse],
    ) -> None:
        """
        Ensure every response contains content.
        """

        for response in responses:
            if not response.content.strip():
                raise EmptyContentError(
                    agent_name=response.agent_name,
                )
