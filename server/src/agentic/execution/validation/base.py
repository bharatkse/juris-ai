"""
Base validation contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from core.dto.agent import AgentResponseDTO


class BaseValidator(ABC):
    """
    Base contract for response validators.
    """

    @abstractmethod
    async def validate(
        self,
        *,
        responses: Sequence[AgentResponseDTO],
    ) -> None:
        """
        Validate one or more agent responses.

        Raises:
            ValidationError
        """

        raise NotImplementedError
