"""
Base validation contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.orchestration.response import AgentResponse


class BaseValidator(ABC):
    """
    Base contract for response validators.
    """

    @abstractmethod
    async def validate(
        self,
        *,
        responses: Sequence[AgentResponse],
    ) -> None:
        """
        Validate one or more agent responses.

        Raises:
            ValidationError
        """

        raise NotImplementedError
