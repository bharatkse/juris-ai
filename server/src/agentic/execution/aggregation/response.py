"""
Response aggregator.
"""

from __future__ import annotations

from collections.abc import Sequence

from adapters.observability.logger import get_logger
from agentic.execution.aggregation.base import BaseAggregator
from agentic.execution.aggregation.schemas import (
    AggregatedResponse,
    AggregationMetadata,
    AggregationResult,
)
from core.dto.agent import AgentResponseDTO
from core.dto.response import CitationDTO, SourceDTO
from core.exceptions.aggregation import EmptyAggregationError

logger = get_logger(__name__)


class ResponseAggregator(BaseAggregator):
    """
    Aggregates responses produced by one or more agents.
    """

    async def aggregate(
        self,
        responses: Sequence[AgentResponseDTO],
    ) -> AggregationResult:
        """
        Aggregate agent responses into a single response.
        """

        if not responses:
            logger.error("No responses to aggregate. Response: %s", responses)
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
        responses: Sequence[AgentResponseDTO],
    ) -> str:
        """
        Aggregate response content.
        """

        return "\n\n".join(
            response.content.strip() for response in responses if response.content.strip()
        )

    @staticmethod
    def _aggregate_citations(
        responses: Sequence[AgentResponseDTO],
    ) -> list:
        """
        Aggregate response citations.
        """

        citations: list[CitationDTO] = []

        for response in responses:
            citations.extend(
                response.citations,
            )

        return citations

    @staticmethod
    def _aggregate_sources(
        responses: Sequence[AgentResponseDTO],
    ) -> list:
        """
        Aggregate response sources.
        """

        sources: list[SourceDTO] = []

        for response in responses:
            sources.extend(
                response.sources,
            )

        return sources

    @staticmethod
    def _aggregate_metadata(
        responses: Sequence[AgentResponseDTO],
    ) -> AggregationMetadata:
        """
        Aggregate metadata from all agent responses.
        """

        agents = [response.agent_name for response in responses]

        # First non-None value wins across responses.
        termination_reason = next(
            (
                response.metadata.get("termination_reason")
                for response in responses
                if response.metadata.get("termination_reason") is not None
            ),
            None,
        )
        groundedness = next(
            (
                response.metadata.get("groundedness")
                for response in responses
                if response.metadata.get("groundedness") is not None
            ),
            None,
        )
        relevance = next(
            (
                response.metadata.get("relevance")
                for response in responses
                if response.metadata.get("relevance") is not None
            ),
            None,
        )

        return AggregationMetadata(
            agents=agents,
            merged_responses=len(responses),
            termination_reason=termination_reason,
            groundedness=groundedness,
            relevance=relevance,
        )
