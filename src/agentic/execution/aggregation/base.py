"""
Base aggregation contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from agentic.execution.aggregation.schemas import AggregatedResponse
from agentic.orchestration.schemas.response import AgentResponse


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
        responses: Sequence[AgentResponse],
    ) -> AggregatedResponse:
        """
        Aggregate multiple agent responses into a single response.
        """

        raise NotImplementedError
