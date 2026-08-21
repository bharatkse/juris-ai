"""
AI orchestrator.

Coordinates the AI request lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.dto.action import ActionRequestDTO
from src.core.dto.agent import AgentContextDTO, AgentResponseDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.message import MessageDTO
from src.core.enums import ExecutionStatusEnum, MessageRoleEnum
from src.core.exceptions.execution import ExecutionError
from src.core.logger import get_logger
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

if TYPE_CHECKING:
    from src.authorization.service import AuthorizationService
    from src.execution.aggregation.response import ResponseAggregator
    from src.execution.executor import Executor
    from src.execution.validation.response import ResponseValidator
    from src.planning.planner import ExecutionPlanner


log = get_logger(__name__)


class AIOrchestrator:
    """
    Coordinates the AI request lifecycle.

    Responsibilities:

    - Build orchestration context.
    - Authorize the user request.
    - Create the execution plan.
    - Execute the plan.
    - Validate agent responses.
    - Aggregate the execution result.
    - Return the final response and any proposed action.

    The orchestrator does not:

    - persist actions,
    - perform action authorization,
    - create approval requests,
    - wait for human approval,
    - execute tools directly,
    - resume an execution session after approval.
    """

    def __init__(
        self,
        *,
        planner: ExecutionPlanner,
        executor: Executor,
        validator: ResponseValidator,
        aggregator: ResponseAggregator,
        authorization: AuthorizationService,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._validator = validator
        self._aggregator = aggregator
        self._authorization = authorization

    async def handle(
        self,
        *,
        request: OrchestratorRequest,
    ) -> OrchestratorResponse:
        """
        Execute the complete orchestration lifecycle.

        Normal chat:

            request
                -> authorize request
                -> plan
                -> execute
                -> validate
                -> aggregate
                -> response

        Action:

            request
                -> authorize request
                -> plan
                -> execute
                -> validate
                -> aggregate
                -> response + ActionRequestDTO

        Action persistence, action authorization, and approval
        processing are handled outside the orchestrator.
        """

        log.info(
            "Starting AI orchestration.",
            extra={
                "operation": "orchestrate",
                "request_id": str(request.request_id),
                "conversation_id": str(request.conversation_id),
                "user_id": str(request.user_id),
                "event_id": request.current_event_id,
            },
        )

        with span(
            "juris_ai.orchestration",
            attributes={
                "request.id": str(request.request_id),
                "conversation.id": str(request.conversation_id),
                "event.id": request.request_id,
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

                # ---------------------------------------------------------
                # 1. Request-level authorization
                # ---------------------------------------------------------

                self._authorization.authorize_request(
                    user_id=request.user_id,
                    message=request.message,
                )

                log.debug(
                    "Request authorization completed.",
                    extra={
                        "operation": "authorize_request",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "user_id": str(request.user_id),
                    },
                )

                # ---------------------------------------------------------
                # 2. Planning
                # ---------------------------------------------------------

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

                # ---------------------------------------------------------
                # 3. Build execution context
                # ---------------------------------------------------------

                conversation = self._build_conversation(
                    request=request,
                )

                context = AgentContextDTO(
                    uploaded_files=tuple(request.attachments),
                )

                # ---------------------------------------------------------
                # 4. Execute reasoning workflow
                # ---------------------------------------------------------

                execution_result = await self._executor.execute(
                    request_id=request.request_id,
                    conversation=conversation,
                    plan=execution_plan,
                    context=context,
                )

                if execution_result.state.status is ExecutionStatusEnum.FAILED:
                    raise ExecutionError(
                        message="Execution failed.",
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

                # ---------------------------------------------------------
                # 5. Extract and validate agent responses
                # ---------------------------------------------------------

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

                # ---------------------------------------------------------
                # 6. Aggregate
                #
                # This produces the final draft response.
                # ---------------------------------------------------------

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

                # ---------------------------------------------------------
                # 7. Build response
                #
                # The orchestrator returns the concrete action request
                # when execution produced one.
                #
                # The request does not own a persistent action ID.
                # ActionWorkflowService is responsible for persistence.
                # ---------------------------------------------------------

                action_request: ActionRequestDTO | None = execution_result.action

                orchestrator_response = OrchestratorResponse(
                    conversation_id=request.conversation_id,
                    content=aggregation_result.response.content,
                    citations=aggregation_result.response.citations,
                    sources=aggregation_result.response.sources,
                    usage=aggregation_result.response.metadata.usage,
                    action=action_request,
                )

                if action_request is None:
                    log.info(
                        "Normal chat response completed.",
                        extra={
                            "operation": "orchestrate",
                            "request_id": str(request.request_id),
                            "conversation_id": str(request.conversation_id),
                            "action_required": False,
                        },
                    )

                    return orchestrator_response

                log.info(
                    "Concrete action proposed.",
                    extra={
                        "operation": "action_proposed",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "event_id": request.current_event_id,
                        "tool_name": action_request.tool_name,
                        "action_type": action_request.action_type.value,
                        "agent_id": action_request.agent_id,
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
