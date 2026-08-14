"""
AI orchestrator.

Coordinates the complete AI request lifecycle.
"""

from __future__ import annotations

from src.aggregation.response import ResponseAggregator
from src.core.dto.agent import AgentResponseDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.message import MessageDTO
from src.core.enums import MessageRoleEnum
from src.core.logger import get_logger
from src.execution.executor import Executor
from src.observability.tracing import span
from src.orchestration.schemas.context import (
    ConversationContext,
    DocumentContext,
    OrchestrationContext,
    RequestContext,
    RuntimeContext,
    UserContext,
)
from src.orchestration.schemas.request import OrchestratorRequest
from src.orchestration.schemas.response import OrchestratorResponse
from src.planning.planner import ExecutionPlanner
from src.validation.response import ResponseValidator

log = get_logger(__name__)


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

        log.info(
            "Starting AI orchestration.",
            extra={
                "operation": "orchestrate",
                "request_id": str(request.request_id),
                "conversation_id": str(request.conversation_id),
                "user_id": str(request.user_id),
            },
        )

        with span(
            "juris_ai.orchestration",
            attributes={
                "request.id": str(request.request_id),
                "conversation.id": str(request.conversation_id),
            },
        ) as current_span:
            try:
                orchestration_context = self._build_context(
                    request=request,
                )

                log.debug(
                    "Orchestration context built.",
                    extra={
                        "operation": "build_context",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "history_count": len(request.history),
                        "attachment_count": len(request.attachments),
                    },
                )

                execution_plan = await self._planner.create_plan(
                    context=orchestration_context,
                )

                current_span.set_attribute(
                    "execution.intent",
                    execution_plan.intent,
                )
                current_span.set_attribute(
                    "execution.mode",
                    execution_plan.mode,
                )
                current_span.set_attribute(
                    "execution.step_count",
                    len(execution_plan.steps),
                )

                log.info(
                    "Execution plan created.",
                    extra={
                        "operation": "create_plan",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "intent": execution_plan.intent,
                        "mode": execution_plan.mode,
                        "step_count": len(execution_plan.steps),
                    },
                )

                conversation = self._build_conversation(
                    request=request,
                )

                log.debug(
                    "Execution conversation built.",
                    extra={
                        "operation": "build_conversation",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "message_count": len(conversation.messages),
                    },
                )

                execution_result = await self._executor.execute(
                    request_id=request.request_id,
                    conversation=conversation,
                    plan=execution_plan,
                )

                log.info(
                    "Execution completed.",
                    extra={
                        "operation": "execute_plan",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "mode": execution_plan.mode,
                    },
                )

                agent_responses = self._extract_agent_responses(
                    execution_result=execution_result,
                )

                await self._validator.validate(
                    responses=agent_responses,
                )

                log.debug(
                    "Agent responses validated.",
                    extra={
                        "operation": "validate_responses",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "response_count": len(agent_responses),
                    },
                )

                aggregation_result = await self._aggregator.aggregate(
                    responses=agent_responses,
                )

                log.debug(
                    "Agent responses aggregated.",
                    extra={
                        "operation": "aggregate_responses",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                    },
                )

                orchestrator_response = OrchestratorResponse(
                    conversation_id=request.conversation_id,
                    content=aggregation_result.response.content,
                    citations=aggregation_result.response.citations,
                    sources=aggregation_result.response.sources,
                    usage=aggregation_result.response.metadata.usage,
                )

                log.info(
                    "AI orchestration completed.",
                    extra={
                        "operation": "orchestrate",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "citation_count": len(
                            orchestrator_response.citations,
                        ),
                        "source_count": len(
                            orchestrator_response.sources,
                        ),
                    },
                )

                return orchestrator_response

            except Exception:
                log.exception(
                    "AI orchestration failed.",
                    extra={
                        "operation": "orchestrate",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "user_id": str(request.user_id),
                    },
                )
                raise

    @staticmethod
    def _extract_agent_responses(
        *,
        execution_result,
    ) -> tuple[AgentResponseDTO, ...]:
        """
        Extract successful agent responses from an execution result.
        """

        return tuple(
            artifact
            for artifact in execution_result.artifacts.values()
            if isinstance(
                artifact,
                AgentResponseDTO,
            )
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
                history=request.history,
            ),
            user=UserContext(
                user_id=request.user_id,
            ),
            documents=DocumentContext(
                attachments=request.attachments,
            ),
            runtime=RuntimeContext(),
        )

    @staticmethod
    def _build_conversation(
        *,
        request: OrchestratorRequest,
    ) -> ConversationDTO:
        """
        Build the conversation used during execution.

        The conversation contains historical messages followed by
        the current user message.
        """

        messages = [
            MessageDTO(
                role=message.role,
                content=message.content,
            )
            for message in request.history
        ]

        messages.append(
            MessageDTO(
                role=MessageRoleEnum.USER,
                content=request.message,
            ),
        )

        return ConversationDTO(
            messages=tuple(messages),
        )
