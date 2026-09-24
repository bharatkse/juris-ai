"""
AI orchestrator.

Coordinates the AI request lifecycle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING

from adapters.observability.logger import get_logger
from adapters.observability.tracing import span
from agentic.execution.aggregation.schemas import AggregationMetadata
from agentic.execution.schemas.result import ExecutionResultSchema
from agentic.guardrails.schemas import GuardrailActionEnum, GuardrailReviewResult
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
    Citation,
    GuardrailInfo,
    OrchestratorResponse,
    OrchestratorStreamChunk,
    ResponseMetadata,
    Source,
    Usage,
)
from core.dto.agent import AgentContextDTO, AgentResponseDTO, AgentStreamChunkDTO
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
    from agentic.guardrails.service import OutputGuardrailService
    from agentic.planning.planner import ExecutionPlanner
    from application.authorization.service import AuthorizationService
    from application.services.action_workflow import ActionWorkflowService
    from application.services.compliance_log import StandaloneComplianceLogWriter
    from core.dto.planning import ExecutionPlanDTO

log = get_logger(__name__)

# Fixed fallback content for a response an output guardrail blocked
# and could not clear even after regeneration -- same "fixed,
# never-regenerated" shape as the EmptyAggregationError fallback below
# (a tool/execution failure), not another LLM call (which could just
# reproduce the same harmful content again).
_GUARDRAIL_BLOCKED_MESSAGE = (
    "I'm not able to provide a response to this request. If you believe "
    "this is a mistake, please rephrase your question or contact support."
)


def _evidence_text(
    *,
    agent_responses: Sequence[AgentResponseDTO],
    citations: Sequence[Citation],
    sources: Sequence[Source],
) -> str:
    """
    Build the text OutputGuardrailService checks PII provenance
    against (see agentic/guardrails/pii.py's evidence-matched logic).

    Prefers each response's real, untruncated retrieved-evidence text
    -- threaded through AgentResponseDTO.metadata["evidence_text"] by
    AgentResponseMapper.map(), the exact same handle.reasoning_context
    content AgentContinuationService._gate_final evaluated the answer
    against. Previously this function only had citation snippets
    (280-char truncated excerpts) and source titles to work with,
    since the full evidence never left agentic.agents.runtime -- that
    gap is what metadata["evidence_text"] closes. Citations/sources
    remain a fallback for the case no response carried evidence_text
    (e.g. a FINAL answer with no retrieval at all), not the primary
    source anymore.
    """

    evidence_parts = [
        text for response in agent_responses if (text := response.metadata.get("evidence_text"))
    ]

    if evidence_parts:
        return "\n".join(evidence_parts)

    parts = [item.snippet for item in citations if item.snippet]
    parts.extend(item.title for item in sources if item.title)

    return "\n".join(parts)


def _build_guardrail_info(
    result: GuardrailReviewResult,
) -> GuardrailInfo | None:
    """
    Build the OrchestratorResponse.guardrail payload, or None when
    nothing fired -- a plain chat turn shouldn't grow a stored
    {"action": "none", ...} on every single response.
    """

    if result.action is GuardrailActionEnum.NONE:
        return None

    return GuardrailInfo(
        action=result.action,
        detection_count=len(result.detections),
        categories=sorted({detection.entity_type for detection in result.detections}),
        harmful=bool(result.harmful and result.harmful.harmful),
        harmful_category=(result.harmful.category if result.harmful else None),
    )


def _to_response_metadata(
    metadata: AggregationMetadata,
) -> ResponseMetadata:
    """
    Carry AggregationMetadata's per-turn signals (agents,
    termination_reason, groundedness, relevance) through to
    OrchestratorResponse.metadata. Every OrchestratorResponse(...)
    construction below used to omit metadata= entirely, so this data
    -- present on AgentResponseDTO.metadata since AgentResponseMapper
    builds it -- never survived past aggregation. usage is carried
    separately at each call site
    (aggregation_result.response.metadata.usage), not duplicated
    here.
    """

    return ResponseMetadata(
        agents=metadata.agents,
        termination_reason=metadata.termination_reason,
        groundedness=metadata.groundedness,
        relevance=metadata.relevance,
    )


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
    - Review the aggregated response through output guardrails
      (PII redaction, harmful-content blocking) before it leaves.
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
        guardrails: OutputGuardrailService,
        compliance_log: StandaloneComplianceLogWriter,
        guardrail_max_regenerate_attempts: int = 1,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._validator = validator
        self._aggregator = aggregator
        self._authorization = authorization
        self._guardrails = guardrails
        self._compliance_log = compliance_log
        self._guardrail_max_regenerate_attempts = guardrail_max_regenerate_attempts

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

        # A single guardrail pass, not the bounded regenerate loop
        # handle() runs on a BLOCKED verdict: resuming a HITL-paused
        # execution already carries a real human decision (approve/
        # reject/edit) attached to it -- discarding that to re-run
        # generation from scratch on a fresh thread would be a much
        # bigger behavior change than this guardrail is meant to make.
        # A BLOCKED verdict here falls straight to the fixed refusal
        # instead.
        guardrail_result = await self._guardrails.review(
            content=aggregation_result.response.content,
            evidence_text=_evidence_text(
                agent_responses=agent_responses,
                citations=aggregation_result.response.citations,
                sources=aggregation_result.response.sources,
            ),
        )

        if guardrail_result.action is GuardrailActionEnum.BLOCKED:
            log.warning(
                "Output guardrail blocked a resumed response.",
                extra={
                    "operation": "resume",
                    "thread_id": thread_id,
                    "harmful_category": (
                        guardrail_result.harmful.category if guardrail_result.harmful else None
                    ),
                },
            )

            return OrchestratorResponse(
                conversation_id=conversation_id,
                content=_GUARDRAIL_BLOCKED_MESSAGE,
                citations=[],
                sources=[],
                usage=Usage(),
                action=_to_action_request(execution_result.action),
                approval=_to_approval_response(execution_result.approval),
                guardrail=_build_guardrail_info(guardrail_result),
            )

        return OrchestratorResponse(
            conversation_id=conversation_id,
            content=guardrail_result.content,
            citations=aggregation_result.response.citations,
            sources=aggregation_result.response.sources,
            usage=aggregation_result.response.metadata.usage,
            metadata=_to_response_metadata(aggregation_result.response.metadata),
            action=_to_action_request(execution_result.action),
            approval=_to_approval_response(execution_result.approval),
            guardrail=_build_guardrail_info(guardrail_result),
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

                await self._compliance_log.record_plan_created(
                    request_id=request.request_id,
                    user_id=str(request.user_id),
                    tenant_id=str(request.user_id),
                    conversation_id=str(request.conversation_id),
                    intent=str(execution_plan.intent),
                    mode=str(execution_plan.mode),
                    step_count=len(execution_plan.steps),
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
                    request_id=str(request.request_id),
                )

                # ---------------------------------------------------------
                # 4-6b. Execute -> validate -> aggregate -> guardrail
                #
                # Runs in a bounded loop: a harmful-content BLOCKED
                # verdict (6b) triggers one full regeneration on a
                # fresh thread_id (never a replay of the blocked run --
                # see the comment below) before falling back to a fixed
                # refusal. A response carrying a pending action (a
                # gated tool call awaiting human approval) never enters
                # the regenerate branch -- see the comment at 6b.
                # ---------------------------------------------------------

                max_attempts = self._guardrail_max_regenerate_attempts + 1

                for attempt in range(1, max_attempts + 1):
                    attempt_context = (
                        context
                        if attempt == 1
                        else AgentContextDTO(
                            user_id=context.user_id,
                            # A NEW thread_id, deliberately -- reusing
                            # the original would make this a LangGraph
                            # resume/replay of the blocked run rather
                            # than an independent regeneration attempt,
                            # and could re-surface the same cached,
                            # already-blocked FINAL answer via
                            # checkpointed replay (see continuation.py's
                            # extensive replay-safety notes on why
                            # thread_id identity matters here).
                            execution_id=context.execution_id,
                            thread_id=f"{context.thread_id}:guardrail-retry-{attempt}",
                            conversation_event_id=context.conversation_event_id,
                            uploaded_files=context.uploaded_files,
                            # Same real request across every attempt --
                            # see AgentContextDTO.request_id's docstring.
                            request_id=context.request_id,
                        )
                    )

                    # ---------------------------------------------------------
                    # 4. Execute reasoning workflow
                    # ---------------------------------------------------------

                    execution_result = await self._executor.execute(
                        request_id=request.request_id,
                        conversation=conversation,
                        plan=execution_plan,
                        context=attempt_context,
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

                    # A terminal decision with no mappable agent response
                    # can happen for several distinct reasons -- a tool
                    # call, policy check, or validation failing (FAILED),
                    # a budget/iteration/timeout limit hit mid-
                    # continuation (PARTIAL), or in principle a terminal
                    # decision type AgentExecutionNode does not map to an
                    # artifact reaching the graph boundary (COMPLETED) --
                    # see nodes.py, which maps FINAL and NEED_INPUT today.
                    # ResponseAggregator.aggregate() raises
                    # EmptyAggregationError on an empty responses tuple --
                    # previously uncaught here, surfacing as an unhandled
                    # 500 for what can be an ordinary, expected outcome.
                    # Same fallback shape as AIOrchestrator.resume() uses
                    # for a rejected/failed gated action. A fixed fallback
                    # string like this needs no guardrail review.
                    if not agent_responses:
                        step_termination_reasons = tuple(
                            step.termination_reason
                            for step in execution_result.state.steps.values()
                            if step.termination_reason
                        )
                        step_errors = tuple(
                            step.error
                            for step in execution_result.state.steps.values()
                            if step.error
                        )

                        log.error(
                            "Execution ended without a mappable agent "
                            "response -- returning a graceful fallback "
                            "instead of raising EmptyAggregationError. "
                            "See execution_status/termination_reasons/"
                            "step_errors for the actual cause -- this is "
                            "not always a tool call failing.",
                            extra={
                                "operation": "orchestrate",
                                "request_id": str(request.request_id),
                                "conversation_id": str(request.conversation_id),
                                "execution_status": execution_result.state.status.value,
                                "termination_reasons": step_termination_reasons,
                                "step_errors": step_errors,
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

                    # Compliance log: what each agent decided. Only
                    # FINAL decisions ever reach agent_responses (see
                    # _extract_agent_responses), so decision_type is
                    # fixed here. groundedness/relevance come from
                    # AgentContinuationService._gate_final's accepted
                    # evaluation, threaded up through AgentResponseDTO.
                    # metadata (see AgentResponseMapper.map() and
                    # AnswerEvaluationSummary's docstring) -- None when
                    # no evaluation was ever accepted for this response
                    # (e.g. an empty FINAL answer, which _gate_final
                    # skips evaluating entirely).
                    for agent_response in agent_responses:
                        await self._compliance_log.record_agent_decision(
                            request_id=request.request_id,
                            user_id=str(request.user_id),
                            tenant_id=str(request.user_id),
                            conversation_id=str(request.conversation_id),
                            agent_id=agent_response.agent_name,
                            decision_type="final",
                            groundedness=agent_response.metadata.get("groundedness"),
                            relevance=agent_response.metadata.get("relevance"),
                        )

                    # ---------------------------------------------------------
                    # 6b. Output guardrail review
                    # ---------------------------------------------------------

                    action_request: AgentActionRequestDTO | None = _to_action_request(
                        execution_result.action
                    )

                    guardrail_result = await self._guardrails.review(
                        content=aggregation_result.response.content,
                        evidence_text=_evidence_text(
                            agent_responses=agent_responses,
                            citations=aggregation_result.response.citations,
                            sources=aggregation_result.response.sources,
                        ),
                    )

                    if guardrail_result.action is not GuardrailActionEnum.NONE:
                        await self._compliance_log.record_guardrail_fired(
                            request_id=request.request_id,
                            user_id=str(request.user_id),
                            tenant_id=str(request.user_id),
                            conversation_id=str(request.conversation_id),
                            action=guardrail_result.action.value,
                            detection_count=len(guardrail_result.detections),
                            categories=sorted({d.entity_type for d in guardrail_result.detections}),
                            harmful=bool(
                                guardrail_result.harmful and guardrail_result.harmful.harmful
                            ),
                            harmful_category=(
                                guardrail_result.harmful.category
                                if guardrail_result.harmful
                                else None
                            ),
                        )

                    if guardrail_result.action is not GuardrailActionEnum.BLOCKED:
                        break

                    if action_request is not None:
                        # A pending action awaiting human approval is
                        # already attached to this attempt -- do not
                        # discard it by regenerating from scratch (see
                        # the loop's docstring). Accept the BLOCKED
                        # verdict as final for this attempt instead of
                        # looping.
                        break

                    if attempt == max_attempts:
                        log.error(
                            "Output guardrail blocked the response after "
                            "%d attempt(s); returning a fixed refusal.",
                            attempt,
                            extra={
                                "operation": "orchestrate",
                                "request_id": str(request.request_id),
                                "conversation_id": str(request.conversation_id),
                                "harmful_category": (
                                    guardrail_result.harmful.category
                                    if guardrail_result.harmful
                                    else None
                                ),
                            },
                        )
                        break

                    log.warning(
                        "Output guardrail blocked a response; " "regenerating (attempt %d of %d).",
                        attempt,
                        max_attempts,
                        extra={
                            "operation": "orchestrate",
                            "request_id": str(request.request_id),
                            "conversation_id": str(request.conversation_id),
                        },
                    )

                # ---------------------------------------------------------
                # 7. Build response
                # ---------------------------------------------------------

                if guardrail_result.action is GuardrailActionEnum.BLOCKED:
                    return OrchestratorResponse(
                        conversation_id=request.conversation_id,
                        content=_GUARDRAIL_BLOCKED_MESSAGE,
                        citations=[],
                        sources=[],
                        usage=Usage(),
                        action=action_request,
                        approval=_to_approval_response(execution_result.approval),
                        guardrail=_build_guardrail_info(guardrail_result),
                    )

                orchestrator_response = OrchestratorResponse(
                    conversation_id=request.conversation_id,
                    content=guardrail_result.content,
                    citations=aggregation_result.response.citations,
                    sources=aggregation_result.response.sources,
                    usage=aggregation_result.response.metadata.usage,
                    metadata=_to_response_metadata(aggregation_result.response.metadata),
                    action=action_request,
                    approval=_to_approval_response(execution_result.approval),
                    guardrail=_build_guardrail_info(guardrail_result),
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

    async def stream(
        self,
        *,
        request: OrchestratorRequest,
        action_workflow_service: ActionWorkflowService,
    ) -> AsyncIterator[OrchestratorStreamChunk]:
        """
        Streaming counterpart to handle() above.

        Planning, authorization, the regenerate loop's structure, and
        response-building are identical to handle() -- see that
        method's docstring for the base lifecycle. The differences are
        all about how the FINAL step's answer reaches the caller:

        Each regenerate-loop attempt calls Executor.execute_streaming()
        instead of execute(), but its output (AgentStreamChunkDTO
        chunks, then one ExecutionResultSchema) is fully buffered
        here, not forwarded -- nothing reaches this method's own
        caller until the loop has fully resolved (cleared, accepted-
        blocked with a pending action, or out of attempts). This is
        the whole point: a caller must never see a partial answer from
        an attempt that gets thrown away and regenerated. It costs
        latency before the first chunk goes out (the system has to
        finish confirming an attempt won't be discarded first) --
        an accepted, deliberate tradeoff, not an oversight.

        Once resolved, what actually reaches the caller depends on the
        winning attempt's guardrail verdict:

        - NONE or FLAGGED (content unmodified from what was
          generated): the buffered chunks are replayed verbatim, then
          one empty is_final=True chunk carries the full
          OrchestratorResponse -- content is empty there deliberately,
          since the caller already received it incrementally via the
          replayed chunks; repeating it would duplicate the text for
          an append-based consumer.
        - REDACTED (content modified by PII redaction) or BLOCKED: the
          buffered chunks are discarded entirely and never reach the
          caller. Redacted content differs from what was actually
          streamed during generation -- replaying the pre-redaction
          chunks would leak the exact PII redaction exists to prevent,
          just moved into the streaming path instead of prevented by
          it. A single is_final=True chunk carries the correct
          (redacted, or fixed-refusal) content instead, matching
          handle()'s non-streaming behavior for these two cases
          exactly, just delivered over the stream as one chunk.

        aggregate()/validate() are the exact same calls handle() makes
        (reusing agent_responses extracted from the same
        ExecutionResultSchema shape execute_streaming() and execute()
        both produce via the same underlying _finish()) -- usage and
        citations on the terminal chunk are therefore built identically
        to handle()'s, not a second, parallel computation that could
        drift from it.
        """

        log.info(
            "Starting streaming AI orchestration.",
            extra={
                "operation": "orchestrate_stream",
                "request_id": str(request.request_id),
                "conversation_id": str(request.conversation_id),
                "user_id": str(request.user_id),
                "event_id": request.current_event_id,
            },
        )

        with span(
            "juris_agentic.orchestration_stream",
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

                self._authorization.authorize_request(
                    user_id=request.user_id,
                    message=request.message,
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

                await self._compliance_log.record_plan_created(
                    request_id=request.request_id,
                    user_id=str(request.user_id),
                    tenant_id=str(request.user_id),
                    conversation_id=str(request.conversation_id),
                    intent=str(execution_plan.intent),
                    mode=str(execution_plan.mode),
                    step_count=len(execution_plan.steps),
                )

                conversation = self._build_conversation(
                    request=request,
                )

                context = AgentContextDTO(
                    user_id=request.user_id,
                    execution_id=str(request.current_event_id),
                    thread_id=str(request.request_id),
                    conversation_event_id=request.current_event_id,
                    uploaded_files=tuple(request.attachments),
                    request_id=str(request.request_id),
                )

                max_attempts = self._guardrail_max_regenerate_attempts + 1

                for attempt in range(1, max_attempts + 1):
                    attempt_context = (
                        context
                        if attempt == 1
                        else AgentContextDTO(
                            user_id=context.user_id,
                            execution_id=context.execution_id,
                            thread_id=f"{context.thread_id}:guardrail-retry-{attempt}",
                            conversation_event_id=context.conversation_event_id,
                            uploaded_files=context.uploaded_files,
                            request_id=context.request_id,
                        )
                    )

                    # ---------------------------------------------------------
                    # Execute (streaming), fully buffered -- see this
                    # method's own docstring for why nothing is
                    # forwarded here.
                    # ---------------------------------------------------------

                    buffered_chunks: list[AgentStreamChunkDTO] = []
                    execution_result: ExecutionResultSchema | None = None

                    async for item in self._executor.execute_streaming(
                        request_id=request.request_id,
                        conversation=conversation,
                        plan=execution_plan,
                        context=attempt_context,
                        action_workflow_service=action_workflow_service,
                    ):
                        if isinstance(item, ExecutionResultSchema):
                            execution_result = item
                        else:
                            buffered_chunks.append(item)

                    if execution_result is None:
                        raise RuntimeError(
                            "Streaming execution completed without a final result.",
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

                    agent_responses = self._extract_agent_responses(
                        execution_result=execution_result,
                    )

                    # Same fallback as handle() for a tool failure that
                    # ends the turn without ever reaching FINAL -- a
                    # fixed string needs no guardrail review, and
                    # buffered_chunks is guaranteed empty here anyway
                    # (AgentExecutionNode only ever streams a FINAL
                    # decision's answer).
                    if not agent_responses:
                        log.error(
                            "Execution ended without a FINAL response (a "
                            "tool call failed) -- returning a graceful "
                            "fallback instead of raising EmptyAggregationError.",
                            extra={
                                "operation": "orchestrate_stream",
                                "request_id": str(request.request_id),
                                "conversation_id": str(request.conversation_id),
                                "execution_status": execution_result.state.status.value,
                            },
                        )

                        fallback_response = OrchestratorResponse(
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

                        yield OrchestratorStreamChunk(
                            content=fallback_response.content,
                            is_final=True,
                            response=fallback_response,
                        )

                        return

                    await self._validator.validate(
                        responses=agent_responses,
                    )

                    aggregation_result = await self._aggregator.aggregate(
                        responses=agent_responses,
                    )

                    for agent_response in agent_responses:
                        await self._compliance_log.record_agent_decision(
                            request_id=request.request_id,
                            user_id=str(request.user_id),
                            tenant_id=str(request.user_id),
                            conversation_id=str(request.conversation_id),
                            agent_id=agent_response.agent_name,
                            decision_type="final",
                            groundedness=agent_response.metadata.get("groundedness"),
                            relevance=agent_response.metadata.get("relevance"),
                        )

                    action_request: AgentActionRequestDTO | None = _to_action_request(
                        execution_result.action
                    )

                    guardrail_result = await self._guardrails.review(
                        content=aggregation_result.response.content,
                        evidence_text=_evidence_text(
                            agent_responses=agent_responses,
                            citations=aggregation_result.response.citations,
                            sources=aggregation_result.response.sources,
                        ),
                    )

                    if guardrail_result.action is not GuardrailActionEnum.NONE:
                        await self._compliance_log.record_guardrail_fired(
                            request_id=request.request_id,
                            user_id=str(request.user_id),
                            tenant_id=str(request.user_id),
                            conversation_id=str(request.conversation_id),
                            action=guardrail_result.action.value,
                            detection_count=len(guardrail_result.detections),
                            categories=sorted({d.entity_type for d in guardrail_result.detections}),
                            harmful=bool(
                                guardrail_result.harmful and guardrail_result.harmful.harmful
                            ),
                            harmful_category=(
                                guardrail_result.harmful.category
                                if guardrail_result.harmful
                                else None
                            ),
                        )

                    if guardrail_result.action is not GuardrailActionEnum.BLOCKED:
                        break

                    if action_request is not None:
                        break

                    if attempt == max_attempts:
                        log.error(
                            "Output guardrail blocked the response after "
                            "%d attempt(s); returning a fixed refusal.",
                            attempt,
                            extra={
                                "operation": "orchestrate_stream",
                                "request_id": str(request.request_id),
                                "conversation_id": str(request.conversation_id),
                                "harmful_category": (
                                    guardrail_result.harmful.category
                                    if guardrail_result.harmful
                                    else None
                                ),
                            },
                        )
                        break

                    log.warning(
                        "Output guardrail blocked a response; " "regenerating (attempt %d of %d).",
                        attempt,
                        max_attempts,
                        extra={
                            "operation": "orchestrate_stream",
                            "request_id": str(request.request_id),
                            "conversation_id": str(request.conversation_id),
                        },
                    )

                # ---------------------------------------------------------
                # Resolve: emit exactly what handle() would have
                # returned, over the stream.
                #
                # execution_result is reassigned fresh (starting None)
                # on every loop iteration above, which is why mypy
                # can't carry its non-None narrowing this far past the
                # loop on its own -- range(1, max_attempts + 1) always
                # iterates at least once (max_attempts >= 1), and the
                # loop body's own guard already raises before this
                # point if a given attempt's execution_result was ever
                # None, so this is a restatement of an already-enforced
                # guarantee, not a new runtime check.
                # ---------------------------------------------------------

                assert execution_result is not None

                if guardrail_result.action is GuardrailActionEnum.BLOCKED:
                    blocked_response = OrchestratorResponse(
                        conversation_id=request.conversation_id,
                        content=_GUARDRAIL_BLOCKED_MESSAGE,
                        citations=[],
                        sources=[],
                        usage=Usage(),
                        action=action_request,
                        approval=_to_approval_response(execution_result.approval),
                        guardrail=_build_guardrail_info(guardrail_result),
                    )

                    yield OrchestratorStreamChunk(
                        content=blocked_response.content,
                        is_final=True,
                        response=blocked_response,
                    )

                    return

                orchestrator_response = OrchestratorResponse(
                    conversation_id=request.conversation_id,
                    content=guardrail_result.content,
                    citations=aggregation_result.response.citations,
                    sources=aggregation_result.response.sources,
                    usage=aggregation_result.response.metadata.usage,
                    metadata=_to_response_metadata(aggregation_result.response.metadata),
                    action=action_request,
                    approval=_to_approval_response(execution_result.approval),
                    guardrail=_build_guardrail_info(guardrail_result),
                )

                if guardrail_result.action is GuardrailActionEnum.REDACTED:
                    # Content differs from what was actually generated
                    # and buffered -- see this method's docstring for
                    # why the buffered chunks must not be replayed here.
                    yield OrchestratorStreamChunk(
                        content=orchestrator_response.content,
                        is_final=True,
                        response=orchestrator_response,
                    )
                else:
                    # NONE or FLAGGED: content is verbatim what was
                    # streamed -- safe to replay.
                    for chunk in buffered_chunks:
                        yield OrchestratorStreamChunk(
                            content=chunk.content,
                            metadata=dict(chunk.metadata),
                        )

                    yield OrchestratorStreamChunk(
                        content="",
                        is_final=True,
                        response=orchestrator_response,
                    )

                log.info(
                    "Streaming chat response completed.",
                    extra={
                        "operation": "orchestrate_stream",
                        "request_id": str(request.request_id),
                        "conversation_id": str(request.conversation_id),
                        "action_required": action_request is not None,
                    },
                )

            except Exception:
                log.exception(
                    "Streaming AI orchestration failed.",
                    extra={
                        "operation": "orchestrate_stream",
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
                user_memory=request.user_memory,
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
            user_memory=request.user_memory,
        )
