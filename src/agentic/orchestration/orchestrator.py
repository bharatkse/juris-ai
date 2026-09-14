"""
AI orchestrator.

Coordinates the AI request lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.observability.logger import get_logger
from adapters.observability.tracing import span
from agentic.orchestration.schemas.context import (
    ConversationContext,
    DocumentContext,
    OrchestrationContext,
    RequestContext,
    RuntimeContext,
    UserContext,
)
from agentic.orchestration.schemas.request import OrchestratorRequest
from agentic.orchestration.schemas.response import (
    ApprovalResponse,
    OrchestratorResponse,
    Usage,
)
from core.dto.agent import AgentContextDTO, AgentResponseDTO
from core.dto.agent_action import AgentActionRequestDTO, AgentActionResponseDTO
from core.dto.approval import ApprovalResponseDTO
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.enums import ExecutionStatusEnum, MessageRoleEnum

if TYPE_CHECKING:
    # NOTE: fixed from stale pre-layer-reorg paths (authorization.service /
    # services.action_workflow, neither importable today) while adding
    # resume()'s type hints below -- these are TYPE_CHECKING-only, so the
    # wrong paths never actually broke anything at runtime, only silently
    # made this file's type hints unresolvable.
    from agentic.execution.aggregation.response import ResponseAggregator
    from agentic.execution.executor import Executor
    from agentic.execution.validation.response import ResponseValidator
    from agentic.planning.planner import ExecutionPlanner
    from application.authorization.service import AuthorizationService
    from application.services.action_workflow import ActionWorkflowService
    from core.dto.planning import ExecutionPlanDTO

log = get_logger(__name__)


def _to_action_request(
    action: AgentActionResponseDTO | None,
) -> AgentActionRequestDTO | None:
    """
    Convert a persisted, execution-layer AgentActionResponseDTO into
    the lighter AgentActionRequestDTO OrchestratorResponse.action
    actually declares.

    Every OrchestratorResponse construction site below used to pass
    execution_result.action straight through -- the wrong DTO
    (AgentActionResponseDTO has action_id/status/fingerprint that
    AgentActionRequestDTO doesn't) -- which raised a pydantic
    ValidationError the instant action was non-None, i.e. every
    real gated-tool-call turn. Found building the HITL approve-flow
    E2E test (tests/e2e/test_hitl_approval_flow.py), the first test to
    actually exercise this construction with a populated action.
    """

    if action is None:
        return None

    return AgentActionRequestDTO(
        execution_id=action.execution_id,
        thread_id=action.thread_id,
        conversation_event_id=action.conversation_event_id,
        agent_id=action.agent_id,
        action_type=action.action_type,
        actor_type=action.actor_type,
        tool_name=action.tool_name,
        target_agent_id=action.target_agent_id,
        resource_type=action.resource_type,
        resource_id=action.resource_id,
        parameters=action.parameters,
        reason=action.reason,
    )


def _to_approval_response(
    approval: ApprovalResponseDTO | None,
) -> ApprovalResponse | None:
    """
    Convert the persistence-facing ApprovalResponseDTO (core/dto/
    approval.py) into the lightweight, orchestrator-facing
    ApprovalResponse OrchestratorResponse.approval actually declares.
    Same bug/fix rationale as _to_action_request() above.
    """

    if approval is None:
        return None

    return ApprovalResponse(
        approval_id=approval.approval_id,
        status=approval.status,
        expires_at=approval.expires_at,
    )


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

    async def resume(
        self,
        *,
        thread_id: str,
        user_id: str,
        conversation_id: str,
        plan: ExecutionPlanDTO,
        approved: bool,
        tool_name: str,
        parameters: dict[str, object],
        action_workflow_service: ActionWorkflowService,
    ) -> OrchestratorResponse:
        """
        Resume an execution previously paused for human approval of a
        gated (email/slack send) tool call.

        Mirrors handle()'s tail (extract responses -> validate ->
        aggregate -> build response) exactly, since the paused/resumed
        agent turn produces the same AgentResponseDTO shape as a normal
        one once it reaches FINAL. The only difference is how the
        execution result is obtained: Executor.resume() re-enters the
        SAME checkpointed LangGraph thread instead of starting a new
        plan from scratch.
        """

        log.info(
            "Resuming AI orchestration.",
            extra={
                "operation": "resume",
                "thread_id": thread_id,
                "user_id": str(user_id),
                "approved": approved,
                "tool_name": tool_name,
            },
        )

        execution_result = await self._executor.resume(
            thread_id=thread_id,
            user_id=user_id,
            plan=plan,
            action_workflow_service=action_workflow_service,
            approved=approved,
            tool_name=tool_name,
            parameters=parameters,
        )

        agent_responses = self._extract_agent_responses(
            execution_result=execution_result,
        )

        # A rejected (or otherwise failed) tool call ends the turn in a
        # terminal FAILED/PARTIAL state without ever reaching FINAL --
        # AgentContinuationService's TOOL_CALL branch returns
        # handle.terminal_result() directly on tool_result.success=False
        # (continuation.py), which never runs AgentResponseMapper, so
        # execution_result.artifacts has no AgentResponseDTO to extract.
        # ResponseAggregator.aggregate() requires at least one response
        # (EmptyAggregationError otherwise) -- correct for handle()'s
        # first-attempt path, where that would mean something went
        # unexpectedly wrong, but resume() must treat "the human said
        # no" as a normal, expected outcome, not a system failure: the
        # conversation still needs an answer, just not the one that was
        # gated. Same reasoning covers a real tool error surfacing here
        # instead of a rejection.
        if not agent_responses:
            log.info(
                "Resumed execution ended without a FINAL response "
                "(tool call rejected or failed) -- returning a "
                "graceful fallback instead of raising.",
                extra={
                    "operation": "resume",
                    "thread_id": thread_id,
                    "approved": approved,
                    "execution_status": execution_result.state.status.value,
                },
            )

            fallback_content = (
                "I wasn't able to complete this because the request was " "not approved."
                if not approved
                else "I wasn't able to complete this action -- it failed "
                "after approval. Please try again or contact support."
            )

            return OrchestratorResponse(
                conversation_id=conversation_id,
                content=fallback_content,
                citations=[],
                sources=[],
                usage=Usage(),
                action=_to_action_request(execution_result.action),
                approval=_to_approval_response(execution_result.approval),
            )

        await self._validator.validate(
            responses=agent_responses,
        )

        aggregation_result = await self._aggregator.aggregate(
            responses=agent_responses,
        )

        return OrchestratorResponse(
            conversation_id=conversation_id,
            content=aggregation_result.response.content,
            citations=aggregation_result.response.citations,
            sources=aggregation_result.response.sources,
            usage=aggregation_result.response.metadata.usage,
            action=_to_action_request(execution_result.action),
            approval=_to_approval_response(execution_result.approval),
        )

    async def handle(
        self,
        *,
        request: OrchestratorRequest,
        action_workflow_service: ActionWorkflowService,
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
                -> response + AgentActionRequestDTO

        Action persistence, action authorization, and approval
        processing are handled by ActionWorkflowService.
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
            "juris_agentic.orchestration",
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
                    user_id=request.user_id,
                    execution_id=str(request.current_event_id),
                    thread_id=str(request.request_id),
                    conversation_event_id=request.current_event_id,
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
                    action_workflow_service=action_workflow_service,
                )

                if execution_result.state.status is ExecutionStatusEnum.FAILED:
                    failed_steps = [
                        step
                        for step in execution_result.state.steps.values()
                        if step.status is ExecutionStatusEnum.FAILED
                    ]

                    log.error(
                        "Execution failed.",
                        extra={
                            "operation": "orchestrate_execution_failed",
                            "request_id": str(request.request_id),
                            "conversation_id": str(request.conversation_id),
                            "failed_steps": [
                                {
                                    "step_id": step.step_id,
                                    "error": step.error,
                                    "retry_count": step.retry_count,
                                }
                                for step in failed_steps
                            ],
                        },
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

                # A tool call that fails (any tool, not just a gated
                # one -- see AgentContinuationService's TOOL_CALL
                # branch in continuation.py) ends the turn in a
                # terminal FAILED/PARTIAL state without ever reaching
                # FINAL, so AgentResponseMapper never runs and
                # execution_result.artifacts has nothing to extract.
                # ResponseAggregator.aggregate() raises
                # EmptyAggregationError on an empty responses tuple --
                # previously uncaught here, surfacing as an unhandled
                # 500 for what is an ordinary, expected outcome (a
                # tool failed), not a bug in this orchestration code.
                # Same fallback shape as AIOrchestrator.resume() uses
                # for a rejected/failed gated action.
                if not agent_responses:
                    log.error(
                        "Execution ended without a FINAL response (a "
                        "tool call failed) -- returning a graceful "
                        "fallback instead of raising EmptyAggregationError.",
                        extra={
                            "operation": "orchestrate",
                            "request_id": str(request.request_id),
                            "conversation_id": str(request.conversation_id),
                            "execution_status": execution_result.state.status.value,
                        },
                    )

                    return OrchestratorResponse(
                        conversation_id=request.conversation_id,
                        content=(
                            "I wasn't able to complete this request -- "
                            "something went wrong while gathering the "
                            "information needed to answer. Please try "
                            "again."
                        ),
                        citations=[],
                        sources=[],
                        usage=Usage(),
                        action=_to_action_request(execution_result.action),
                        approval=_to_approval_response(execution_result.approval),
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
                # ---------------------------------------------------------

                action_request: AgentActionRequestDTO | None = _to_action_request(
                    execution_result.action
                )

                orchestrator_response = OrchestratorResponse(
                    conversation_id=request.conversation_id,
                    content=aggregation_result.response.content,
                    citations=aggregation_result.response.citations,
                    sources=aggregation_result.response.sources,
                    usage=aggregation_result.response.metadata.usage,
                    action=action_request,
                    approval=_to_approval_response(execution_result.approval),
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
