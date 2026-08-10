"""
AI orchestrator.

Coordinates the complete AI request lifecycle.
"""

from __future__ import annotations

from src.aggregation.response import ResponseAggregator
from src.execution.executor import Executor
from src.orchestration.context import (
    ConversationContext,
    DocumentContext,
    OrchestrationContext,
    RequestContext,
    RuntimeContext,
    UserContext,
)
from src.orchestration.request import OrchestratorRequest
from src.orchestration.response import OrchestratorResponse
from src.planning.planner import ExecutionPlanner
from src.validation.response import ResponseValidator


class AIOrchestrator:
    """
    Coordinates the complete AI request lifecycle.
    """

    def __init__(
        self,
        *,
        planner: ExecutionPlanner,
        executor: Executor,
        validator: ResponseValidator,
        aggregator: ResponseAggregator,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._validator = validator
        self._aggregator = aggregator

    async def handle(
        self,
        *,
        request: OrchestratorRequest,
    ) -> OrchestratorResponse:
        """
        Execute the complete orchestration lifecycle.
        """

        context = self._build_context(
            request=request,
        )

        plan = await self._planner.create_plan(
            context=context,
        )

        responses = await self._executor.execute(
            plan=plan,
            context=context,
        )

        await self._validator.validate(
            responses=responses,
        )

        aggregation = await self._aggregator.aggregate(
            responses=responses,
        )

        return OrchestratorResponse(
            conversation_id=request.conversation_id,
            content=aggregation.response.content,
            citations=aggregation.response.citations,
            sources=aggregation.response.sources,
            usage=aggregation.response.metadata.usage,
        )

    @staticmethod
    def _build_context(
        *,
        request: OrchestratorRequest,
    ) -> OrchestrationContext:
        """
        Build the orchestration context.
        """

        return OrchestrationContext(
            request=RequestContext(
                message=request.message,
            ),
            conversation=ConversationContext(
                conversation_id=request.conversation_id,
            ),
            user=UserContext(
                user_id=request.user_id,
            ),
            documents=DocumentContext(
                attachments=request.attachments,
            ),
            runtime=RuntimeContext(),
        )
