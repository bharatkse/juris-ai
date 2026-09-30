"""
AI orchestrator.

Coordinates the AI request lifecycle.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator, Iterator, Sequence
from contextlib import AbstractContextManager, aclosing, nullcontext
from typing import TYPE_CHECKING

from adapters.observability.logger import get_logger
from adapters.observability.tracing import span
from agentic.agents.prompts.token_budget import estimate_tokens
from agentic.execution.aggregation.schemas import AggregationMetadata
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
from core.deadline import deadline_within
from core.dto.agent import AgentContextDTO, AgentResponseDTO
from core.dto.agent_action import AgentActionRequestDTO, AgentActionResponseDTO
from core.dto.approval import ApprovalResponseDTO
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.enums import ExecutionStatusEnum, MessageRoleEnum
from core.exceptions.planning import PlanTooLargeError
from core.usage import UsageMeter, usage_scope

if TYPE_CHECKING:
    # NOTE: fixed from stale pre-layer-reorg paths (authorization.service /
    # services.action_workflow, neither importable today) while adding
    # resume()'s type hints below -- these are TYPE_CHECKING-only, so the
    # wrong paths never actually broke anything at runtime, only silently
    # made this file's type hints unresolvable.
    from agentic.execution.aggregation.response import ResponseAggregator
    from agentic.execution.executor import Executor
    from agentic.execution.schemas.result import ExecutionResultSchema
    from agentic.execution.validation.response import ResponseValidator
    from agentic.guardrails.service import OutputGuardrailService
    from agentic.planning.planner import ExecutionPlanner
    from agentic.tools.result import ToolResult
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

# Content for a turn that paused on a gated action (email_send/
# slack_post) awaiting the user's approval. The approval itself is
# attached to the same response; without this, a paused single-step plan
# had no FINAL answer and fell through to the "something went wrong"
# fallback next to a perfectly valid pending approval.
_PENDING_APPROVAL_MESSAGE = (
    "This needs your approval before I can continue. Review the pending "
    "request to approve, edit or reject it."
)

_EXECUTION_FAILED_MESSAGE = (
    "I wasn't able to complete this request -- something went wrong while "
    "gathering the information needed to answer. Please try again."
)


def _plan_too_large_response(
    *,
    request: OrchestratorRequest,
    error: PlanTooLargeError,
) -> OrchestratorResponse:
    """
    The reply to a request whose plan has more steps than one turn may
    run (review A7): nothing was executed, and the user is told why and
    what to do, rather than getting an error or a silently cut-down plan.
    """

    log.warning(
        "Execution plan exceeds the step limit; not executing it.",
        extra={
            "operation": "create_plan",
            "request_id": str(request.request_id),
            "conversation_id": str(request.conversation_id),
            "step_count": error.step_count,
            "max_steps": error.max_steps,
        },
    )

    return OrchestratorResponse(
        conversation_id=request.conversation_id,
        content=(
            f"This request would need {error.step_count} steps, but I can run at "
            f"most {error.max_steps} in one turn. Please split it into smaller "
            "questions."
        ),
        citations=[],
        sources=[],
        usage=Usage(),
    )


def _awaiting_approval(execution_result: ExecutionResultSchema) -> bool:
    return (
        execution_result.state.status is ExecutionStatusEnum.WAITING_FOR_APPROVAL
        or execution_result.approval is not None
    )


# Target size of each streamed slice of the reviewed answer. Slices end
# on whitespace, so a word is never split across two chunks.
_STREAM_SLICE_CHARS = 48

_STREAM_TOKEN = re.compile(r"\s*\S+\s*|\s+")


def _raise_if_refused(meter: UsageMeter) -> None:
    """
    End the request if the request token quota refused an LLM call.

    The refusal is raised from inside the LLM call, where a caller may
    turn it into a failed step or a fallback answer (an agent's failed
    turn, a judge failing closed). Whatever happened after it, the
    request stops with the refusal, carrying the tokens used so far.
    """

    if meter.refused is not None:
        raise meter.quota_error()


def _with_usage(response: OrchestratorResponse, meter: UsageMeter) -> OrchestratorResponse:
    """The response with its usage set to the LLM calls counted by meter."""

    return response.model_copy(
        update={
            "usage": Usage(
                provider=meter.provider,
                model=meter.model,
                prompt_tokens=meter.prompt_tokens,
                completion_tokens=meter.completion_tokens,
                total_tokens=meter.total_tokens,
            ),
        },
    )


def _stream_slices(text: str) -> Iterator[str]:
    """
    Split text into consecutive slices of roughly _STREAM_SLICE_CHARS
    characters, breaking only at whitespace. "".join() of the slices
    is exactly `text`.
    """

    current = ""

    for match in _STREAM_TOKEN.finditer(text):
        current += match.group(0)

        if len(current) >= _STREAM_SLICE_CHARS:
            yield current
            current = ""

    if current:
        yield current


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
    builds it -- never survived past aggregation. usage is not
    aggregated from agent responses: handle()/stream()/resume() set it
    from every LLM call the turn made (core.usage).
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
        request_timeout_seconds: float | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._validator = validator
        self._aggregator = aggregator
        self._authorization = authorization
        self._guardrails = guardrails
        self._compliance_log = compliance_log
        self._guardrail_max_regenerate_attempts = guardrail_max_regenerate_attempts
        # The request's deadline (core.deadline), started before planning
        # so planning time counts against it and a planner call sees it
        # (review R18). The graph gets what is left (ExecutionSession).
        # None: no request deadline, only the graph's own timeout.
        self._request_timeout_seconds = request_timeout_seconds

    def request_deadline(self) -> AbstractContextManager[None]:
        """
        The request's deadline, or no deadline if none is configured.

        handle() and stream() open it themselves; a caller that does
        request work before them (ChatService's conversation
        summarization, review G1) opens it first, so that work counts
        against the same deadline (the earlier deadline wins, see
        core.deadline).
        """

        return self._request_deadline()

    def _request_deadline(self) -> AbstractContextManager[None]:
        """The request's deadline, or no deadline if none is configured."""

        if self._request_timeout_seconds is None:
            return nullcontext()

        return deadline_within(self._request_timeout_seconds)

    async def run_approved_tool(
        self,
        *,
        tool_name: str,
        parameters: dict[str, object],
        approval_token: str,
    ) -> ToolResult:
        """
        Run a human-approved gated tool call. Pure delegation to the
        Executor, which owns tool execution (see its docstring); exposed
        here so HitlResumeService depends on the orchestrator alone.
        """

        return await self._executor.run_approved_tool(
            tool_name=tool_name,
            parameters=parameters,
            approval_token=approval_token,
        )

    async def resume(
        self,
        *,
        thread_id: str,
        user_id: str,
        conversation_id: str,
        plan: ExecutionPlanDTO,
        approved: bool,
        tool_result: ToolResult | None,
        action_workflow_service: ActionWorkflowService,
    ) -> OrchestratorResponse:
        """
        Resume an execution paused for approval (see _resume()). The
        response's usage is every LLM call the resumed turn made.
        """

        with usage_scope() as meter:
            response = await self._resume(
                thread_id=thread_id,
                user_id=user_id,
                conversation_id=conversation_id,
                plan=plan,
                approved=approved,
                tool_result=tool_result,
                action_workflow_service=action_workflow_service,
            )

        return _with_usage(response, meter)

    async def handle(
        self,
        *,
        request: OrchestratorRequest,
        action_workflow_service: ActionWorkflowService,
    ) -> OrchestratorResponse:
        """
        Run one chat turn (see _handle()). The response's usage is every
        LLM call the turn made: planner, agents, answer evaluation and
        guardrail judge.
        """

        with usage_scope(estimate_tokens=estimate_tokens) as meter, self._request_deadline():
            try:
                response = await self._handle(
                    request=request,
                    action_workflow_service=action_workflow_service,
                )
            except Exception as exc:
                if meter.refused is not None:
                    raise meter.quota_error() from exc
                raise

        _raise_if_refused(meter)

        return _with_usage(response, meter)

    async def stream(
        self,
        *,
        request: OrchestratorRequest,
        action_workflow_service: ActionWorkflowService,
    ) -> AsyncGenerator[OrchestratorStreamChunk, None]:
        """
        Streaming counterpart to handle() (see _stream()). The final
        chunk's response carries the turn's usage, counted as in
        handle().
        """

        with usage_scope(estimate_tokens=estimate_tokens) as meter, self._request_deadline():
            try:
                # aclosing: when this generator stops early (a refusal),
                # _stream() is closed here, in this context, so its
                # tracing span exits normally.
                async with aclosing(
                    self._stream(
                        request=request,
                        action_workflow_service=action_workflow_service,
                    )
                ) as chunks:
                    async for chunk in chunks:
                        # Every chunk follows the LLM calls it depends on (the
                        # answer is streamed once reviewed), so a refused
                        # call is caught before any text is sent.
                        _raise_if_refused(meter)

                        if chunk.is_final and chunk.response is not None:
                            chunk = chunk.model_copy(
                                update={"response": _with_usage(chunk.response, meter)},
                            )

                        yield chunk
            except Exception as exc:
                if meter.refused is not None:
                    raise meter.quota_error() from exc
                raise

    async def _resume(
        self,
        *,
        thread_id: str,
        user_id: str,
        conversation_id: str,
        plan: ExecutionPlanDTO,
        approved: bool,
        tool_result: ToolResult | None,
        action_workflow_service: ActionWorkflowService,
    ) -> OrchestratorResponse:
        """
        Resume an execution previously paused for human approval of a
        gated (email_send/slack_post) tool call. An approved call has
        already run (run_approved_tool()); tool_result is its result.

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
                "tool_name": tool_result.tool_name if tool_result else None,
            },
        )

        execution_result = await self._executor.resume(
            thread_id=thread_id,
            user_id=user_id,
            plan=plan,
            action_workflow_service=action_workflow_service,
            approved=approved,
            tool_result=tool_result,
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

            if _awaiting_approval(execution_result):
                # The resumed turn went on to propose another gated
                # action, which now waits for its own approval.
                fallback_content = _PENDING_APPROVAL_MESSAGE
            elif not approved:
                fallback_content = (
                    "I wasn't able to complete this because the request was not approved."
                )
            else:
                fallback_content = (
                    "I wasn't able to complete this action -- it failed "
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
            usage=Usage(),
            metadata=_to_response_metadata(aggregation_result.response.metadata),
            action=_to_action_request(execution_result.action),
            approval=_to_approval_response(execution_result.approval),
            guardrail=_build_guardrail_info(guardrail_result),
        )

    async def _handle(
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

                await self._authorization.authorize_request(
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

                try:
                    execution_plan = await self._planner.create_plan(
                        context=orchestration_context,
                    )
                except PlanTooLargeError as exc:
                    return _plan_too_large_response(
                        request=request,
                        error=exc,
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

                        # A pause for approval is expected, not an error.
                        (log.info if _awaiting_approval(execution_result) else log.error)(
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
                                _PENDING_APPROVAL_MESSAGE
                                if _awaiting_approval(execution_result)
                                else _EXECUTION_FAILED_MESSAGE
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
                            answer_verified=agent_response.metadata.get("answer_verified"),
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
                    usage=Usage(),
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

    async def _stream(
        self,
        *,
        request: OrchestratorRequest,
        action_workflow_service: ActionWorkflowService,
    ) -> AsyncGenerator[OrchestratorStreamChunk, None]:
        """
        Streaming counterpart to handle() above.

        Planning, authorization, the regenerate loop's structure, and
        response-building are identical to handle() -- see that
        method's docstring for the base lifecycle. The differences are
        all about how the FINAL step's answer reaches the caller:

        Each regenerate-loop attempt runs the same Executor.execute()
        as handle(); nothing reaches this method's caller until the loop
        has fully resolved (cleared, accepted-blocked with a pending
        action, or out of attempts), so a caller never sees part of an
        attempt that gets thrown away and regenerated.

        Once resolved, what reaches the caller is exactly the text the
        guardrails reviewed and ChatService persists -- never a separate
        generation:

        - NONE, FLAGGED or REDACTED: guardrail_result.content (for NONE
          and FLAGGED, the aggregated, answer-gated text; for REDACTED,
          its redacted form) is sent as consecutive slices, then one
          empty is_final=True chunk carries the full
          OrchestratorResponse. The terminal content is empty because
          the caller already received the text through the slices;
          repeating it would duplicate it for an append-based consumer.
        - BLOCKED: a single is_final=True chunk carries the fixed
          refusal, matching handle().

        Chunk boundaries are slices of the final text, not model tokens:
        the model's output can't be forwarded before it is reviewed.

        aggregate()/validate() are the exact same calls handle() makes
        (reusing agent_responses extracted from the same
        ExecutionResultSchema shape execute_streaming() and execute()
        both produce via the same underlying _finish()) -- citations on
        the terminal chunk are therefore built identically to handle()'s,
        not a second, parallel computation that could drift from it;
        usage is counted the same way by both wrappers (core.usage).
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

                await self._authorization.authorize_request(
                    user_id=request.user_id,
                    message=request.message,
                )

                try:
                    execution_plan = await self._planner.create_plan(
                        context=orchestration_context,
                    )
                except PlanTooLargeError as exc:
                    plan_too_large = _plan_too_large_response(
                        request=request,
                        error=exc,
                    )
                    yield OrchestratorStreamChunk(
                        content=plan_too_large.content,
                        is_final=True,
                        response=plan_too_large,
                    )
                    return

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

                    agent_responses = self._extract_agent_responses(
                        execution_result=execution_result,
                    )

                    # Same fallback as handle() for a tool failure that
                    # ends the turn without ever reaching FINAL -- a
                    # fixed string needs no guardrail review.
                    if not agent_responses:
                        (log.info if _awaiting_approval(execution_result) else log.error)(
                            "Execution ended without a FINAL response (a "
                            "tool call failed or is awaiting approval) -- returning a graceful "
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
                                _PENDING_APPROVAL_MESSAGE
                                if _awaiting_approval(execution_result)
                                else _EXECUTION_FAILED_MESSAGE
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
                            answer_verified=agent_response.metadata.get("answer_verified"),
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
                # ---------------------------------------------------------

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
                    usage=Usage(),
                    metadata=_to_response_metadata(aggregation_result.response.metadata),
                    action=action_request,
                    approval=_to_approval_response(execution_result.approval),
                    guardrail=_build_guardrail_info(guardrail_result),
                )

                # Stream the reviewed text itself (S2): never a second
                # generation the guardrails and answer gate didn't see.
                for text_slice in _stream_slices(orchestrator_response.content):
                    yield OrchestratorStreamChunk(content=text_slice)

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
