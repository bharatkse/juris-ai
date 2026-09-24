"""
Base aggregation contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from agentic.execution.aggregation.schemas import AggregationResult
from core.dto.agent import AgentResponseDTO


class BaseAggregator(ABC):
    """
    Base contract for response aggregators.

    Aggregators are responsible for combining one or more
    agent responses into a single response suitable for
    returning to the client.
    """

    @abstractmethod
    async def aggregate(
        self,
        responses: Sequence[AgentResponseDTO],
    ) -> AggregationResult:
        """
        Aggregate multiple agent responses into a single response.
        """

        raise NotImplementedError
