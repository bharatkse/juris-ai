"""
Response aggregator.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.aggregation.base import BaseAggregator
from src.aggregation.models import (
    AggregatedResponse,
    AggregationMetadata,
    AggregationResult,
)
from src.core.exceptions.aggregation import EmptyAggregationError
from src.orchestration.response import AgentResponse


class ResponseAggregator(BaseAggregator):
    """
    Aggregates responses produced by one or more agents.
    """

    async def aggregate(
        self,
        responses: Sequence[AgentResponse],
    ) -> AggregationResult:
        """
        Aggregate agent responses into a single response.
        """

        if not responses:
            raise EmptyAggregationError()

        return AggregationResult(
            response=AggregatedResponse(
                content=self._aggregate_content(
                    responses,
                ),
                citations=self._aggregate_citations(
                    responses,
                ),
                sources=self._aggregate_sources(
                    responses,
                ),
                metadata=self._aggregate_metadata(
                    responses,
                ),
            ),
        )

    @staticmethod
    def _aggregate_content(
        responses: Sequence[AgentResponse],
    ) -> str:
        """
        Aggregate response content.
        """

        return "\n\n".join(
            response.message.strip() for response in responses if response.message.strip()
        )

    @staticmethod
    def _aggregate_citations(
        responses: Sequence[AgentResponse],
    ) -> list:
        """
        Aggregate response citations.
        """

        citations = []

        for response in responses:
            citations.extend(
                response.citations,
            )

        return citations

    @staticmethod
    def _aggregate_sources(
        responses: Sequence[AgentResponse],
    ) -> list:
        """
        Aggregate response sources.
        """

        sources = []

        for response in responses:
            sources.extend(
                response.sources,
            )

        return sources

    @staticmethod
    def _aggregate_metadata(
        responses: Sequence[AgentResponse],
    ) -> AggregationMetadata:
        """
        Aggregate response metadata.
        """

        usage = responses[-1].usage

        return AggregationMetadata(
            agents=[response.agent_name for response in responses],
            merged_responses=len(
                responses,
            ),
            usage=usage,
        )
