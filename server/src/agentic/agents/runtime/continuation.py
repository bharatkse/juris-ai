"""
Agent continuation after internal agent actions.

This module owns the deterministic continuation loop around
AgentExecutionHandle.

AgentExecution reasons.
ToolExecutionService executes tools.
TerminationReason enumerates possible reasons for agent termination.
CollaborationBus mediates agent delegation.
This service coordinates the two.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from langgraph.config import var_child_runnable_config
from langgraph.func import task as langgraph_task

from agentic.agents.runtime.execution import (
    AgentExecutionHandle,
    AgentExecutionResult,
)
from agentic.agents.runtime.feedback import (
    CORRECTIVE_RETRIEVAL_FEEDBACK,
    EVALUATION_FEEDBACK,
    is_feedback,
    runtime_feedback,
)
from agentic.agents.runtime.lifecycle.termination import (
    AgentExecutionStatus,
    TerminationReason,
)
from agentic.collaboration.bus import CollaborationBus
from agentic.decisions.decision import AgentDecisionType
from agentic.evaluation.answer import (
    AnswerEvaluationResult,
    AnswerEvaluationSummary,
    AnswerEvaluator,
    AnswerQualityPolicy,
)
from agentic.policy.guard import AgentPolicyGuard
from agentic.tools.result import ToolResult
from agentic.tools.retrieval import NON_EVIDENCE_CONTENT
from agentic.tools.runtime.invocation import ToolExecutionService
from agentic.tools.runtime.result_converter import ToolResultConverter
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import ActionTypeEnum, MessageRoleEnum, RetrievalSourceEnum
from core.exceptions.registry import ToolNotFoundError
from core.models.message import AgentMessageSchema

if TYPE_CHECKING:
    # Deferred: application/services/compliance_log.py never needs to
    # be imported at runtime here -- this module only calls methods on
    # an already-constructed writer instance (duck typing), and a real
    # runtime import would run the wrong direction against this
    # project's layering (application/ depends on agentic/, not the
    # reverse -- application.services.chat already imports from
    # agentic.orchestration.orchestrator).
    from application.services.compliance_log import StandaloneComplianceLogWriter


async def _call_replay_safe(task_fn, /, **kwargs):
    """
    Call a langgraph.func.task-decorated function normally (inside a
    real graph invocation, this checkpoints the call -- a later
    interrupt()/resume in the same turn replays the enclosing node but
    returns this call's cached result instead of re-invoking it) or
    call its plain underlying function directly when there is no
    active LangGraph runnable context.

    The fallback matters because @task itself raises RuntimeError
    ("Called get_config outside of a runnable context") the instant
    it's invoked without one -- confirmed by running the real unit
    suite, which constructs AgentContinuationService directly and
    calls its methods standalone, exactly that "no context" case, to
    test decision-quality logic in isolation without spinning up a
    full compiled graph. Preserving that test-in-isolation pattern
    matters more than making @task unconditional; production always
    runs inside a real graph.ainvoke(), so it always takes the
    checkpointed path.

    var_child_runnable_config is LangGraph's own (non-raising) way to
    check for an active context -- get_config() itself only raises,
    it doesn't offer a boolean check.
    """

    if var_child_runnable_config.get() is None:
        return await task_fn.func(**kwargs)

    return await task_fn(**kwargs)


# Broadened relative to RetrieverTool's own default (top_k=5) for a
# corrective retry -- a fresh attempt at more evidence should cast a
# wider net than the original call already did. Not empirically
# tuned; a reasonable, easily-adjusted starting point.
CORRECTIVE_RETRIEVAL_TOP_K = 8

# Returned in place of a FINAL answer that failed the answer-quality gate
# when nothing is left to improve it (S5). Fixed text, never the rejected
# answer: for legal output an unverified answer must not reach the user.
UNVERIFIED_ANSWER_MESSAGE = (
    "I couldn't verify an answer to this question against the available "
    "sources, so I'm not giving one. Try rephrasing the question or naming "
    "the specific act or section you're asking about."
)

# Returned in place of a FINAL answer when evidence is required (A1) but
# retrieval found none to ground it in.
NO_SOURCES_ANSWER_MESSAGE = (
    "I couldn't find any sources in the available legal documents that "
    "address this question, so I can't give a grounded answer. Try "
    "rephrasing the question or naming the specific act or section."
)

# RetrieverTool's own default; the seed is a normal first retrieval, not
# a broadened corrective one (CORRECTIVE_RETRIEVAL_TOP_K).
SEED_RETRIEVAL_TOP_K = 5


@dataclass(slots=True, frozen=True)
class AgentContinuationResult:
    """
    Result of one complete agent continuation sequence.
    """

    result: AgentExecutionResult
    action: AgentActionRequestDTO | None = None
    tool_results: tuple[ToolResult, ...] = ()
    # Populated for a FINAL decision _gate_final accepted
    # (verified=True) or rejected and replaced (verified=False) -- see
    # AnswerEvaluationSummary's docstring.
    evaluation_summary: AnswerEvaluationSummary | None = None


class AgentContinuationService:
    """
    Continue one request-scoped agent execution after internal actions.

    Responsibilities:
        - inspect the agent decision
        - execute TOOL_CALL actions
        - mediate DELEGATE actions through CollaborationBus
        - retain tool results
        - feed tool/delegation results back into the same agent handle
        - request the next bounded reasoning slice
        - stop only on an explicit terminal decision

    This service does not:
        - build LangGraph graphs
        - perform planning
        - own agent lifecycle state
        - mutate global state
        - perform business-action approval
    """

    def __init__(
        self,
        *,
        tool_execution_service: ToolExecutionService,
        collaboration_bus: CollaborationBus,
        answer_evaluator: AnswerEvaluator,
        answer_quality_policy: AnswerQualityPolicy,
        agent_policy_guard: AgentPolicyGuard,
        compliance_log: StandaloneComplianceLogWriter,
    ) -> None:
        self._tool_execution_service = tool_execution_service
        self._collaboration_bus = collaboration_bus
        self._answer_evaluator = answer_evaluator
        self._answer_quality_policy = answer_quality_policy
        self._agent_policy_guard = agent_policy_guard
        self._compliance_log = compliance_log

    async def execute(
        self,
        *,
        handle: AgentExecutionHandle,
        initial_result: AgentExecutionResult,
    ) -> AgentContinuationResult:
        """
        Continue an agent execution until it reaches a terminal result
        or produces a non-internal action for the outer execution layer.
        """

        result = initial_result
        tool_results: list[ToolResult] = []

        while True:
            decision = result.decision

            if decision is None:
                return AgentContinuationResult(
                    result=result,
                    tool_results=tuple(tool_results),
                )

            if decision.decision_type is AgentDecisionType.TOOL_CALL:
                action = result.action

                if action is None or action.tool_name is None:
                    return AgentContinuationResult(
                        result=result,
                        tool_results=tuple(tool_results),
                    )

                step_budget = handle.lifecycle.begin_step()

                if not step_budget.allowed:
                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                if action.action_type is ActionTypeEnum.SEND:
                    tool_result = await self._execute_gated_tool(
                        action=action,
                    )
                else:
                    tool_result = await self._execute_tool(
                        handle=handle,
                        action=action,
                    )

                # Retain the tool result only after the lifecycle confirms
                # that another retained tool-result record is available.
                # This keeps the in-memory continuation result bounded by
                # max_tool_result_records.
                tool_result_budget = handle.lifecycle.record_tool_result()

                if not tool_result_budget.allowed:
                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                tool_results.append(tool_result)

                if not tool_result.success:
                    if tool_result.execution_metadata.get("budget_exceeded"):
                        return AgentContinuationResult(
                            result=handle.terminal_result(),
                            tool_results=tuple(tool_results),
                        )

                    if self._retry_after_tool_failure(
                        handle=handle,
                        tool_result=tool_result,
                    ):
                        result = await handle.reason()
                        continue

                    handle.lifecycle.fail(
                        TerminationReason.FAILED_TOOL,
                    )

                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                context = ToolResultConverter.to_reasoning_context(
                    result=tool_result,
                )

                if not self._record_reasoning_context(
                    handle=handle,
                    context=context,
                ):
                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                if not self._record_progress(
                    handle=handle,
                    context=context,
                ):
                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                result = await handle.reason()
                continue

            if decision.decision_type is AgentDecisionType.DELEGATE:
                action = result.action

                if action is None or not action.is_agent_call:
                    return AgentContinuationResult(
                        result=result,
                        tool_results=tuple(tool_results),
                    )

                step_budget = handle.lifecycle.begin_step()

                if not step_budget.allowed:
                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                delegation_result = await self._delegate(
                    handle=handle,
                    action=action,
                )

                if delegation_result is None:
                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                context = self._delegation_to_reasoning_context(
                    action=action,
                    result=delegation_result,
                )

                if not self._record_reasoning_context(
                    handle=handle,
                    context=context,
                ):
                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                if not self._record_progress(
                    handle=handle,
                    context=context,
                ):
                    return AgentContinuationResult(
                        result=handle.terminal_result(),
                        tool_results=tuple(tool_results),
                    )

                result = await handle.reason()
                continue

            if decision.decision_type is AgentDecisionType.FINAL:
                gated, evaluation_summary = await self._gate_final(
                    handle=handle,
                    result=result,
                )
                if gated is not None:
                    if evaluation_summary is not None:
                        # The gate gave up and replaced the answer: stop
                        # here, never re-gate it (S5).
                        return AgentContinuationResult(
                            result=gated,
                            tool_results=tuple(tool_results),
                            evaluation_summary=evaluation_summary,
                        )
                    result = gated
                    continue
                return AgentContinuationResult(
                    result=result,
                    action=result.action,
                    tool_results=tuple(tool_results),
                    evaluation_summary=evaluation_summary,
                )

            return AgentContinuationResult(
                result=result,
                action=result.action,
                tool_results=tuple(tool_results),
            )

    def _retry_after_tool_failure(
        self,
        *,
        handle: AgentExecutionHandle,
        tool_result: ToolResult,
    ) -> bool:
        """
        Tell the model why its tool call failed so it can correct it, and
        return whether it may reason again.

        The error is ToolExecutionService's sanitized message (fields and
        constraints only). Retrying is bounded by the lifecycle's
        no-progress budget -- the same failure repeating is no progress --
        on top of the tool-call and repeated-action budgets every call
        already goes through. A call a human reviewer rejected is not
        retried: the model would just propose it again.
        """

        if "approval_decision" in tool_result.execution_metadata:
            return False

        feedback = runtime_feedback(
            f"Your call to tool '{tool_result.tool_name}' failed: "
            f"{tool_result.error or 'the tool returned an error.'} "
            "Correct the call, use a different tool, or answer from the "
            "evidence you have.",
        )

        if not self._record_progress(handle=handle, context=(feedback,)):
            return False

        handle.extend_reasoning_context(context=(feedback,))
        return True

    async def _execute_gated_tool(
        self,
        *,
        action: AgentActionRequestDTO,
    ) -> ToolResult:
        """
        Pause for human approval instead of executing a GATED_TOOLS
        (email/slack send) TOOL_CALL directly.

        Calls LangGraph's interrupt() with a plain, JSON-serializable
        dict describing the proposed action -- not the AgentActionRequestDTO
        itself, since the checkpointer's msgpack serializer only accepts
        registered/primitive types (a dataclass round-trips today via a
        pickle fallback LangGraph warns is being removed).

        On the pausing call, interrupt() never returns -- it unwinds the
        whole async call stack up through LangGraph's own executor,
        which checkpoints this node's state and returns
        graph_state["__interrupt__"] to whoever called graph.ainvoke().
        See ExecutionSession._prepare_action(), which turns that payload
        into a real AgentActionRequestDTO and a persisted Approval via
        the existing ActionWorkflowService/ApprovalLifecyclePolicy path.

        On resume (a later graph.ainvoke(Command(resume=...), ...) call
        for the same thread_id -- see Executor.resume()), interrupt()
        returns the resume payload instead of pausing, and this method
        returns normally with the tool result that was actually computed
        outside the graph (the approved tool call is executed for real
        by Executor.resume() BEFORE resuming, not replayed inside this
        node -- see its docstring for why).

        LangGraph replays this WHOLE node function from the top on
        resume -- including any tool call that ran earlier in the SAME
        agent turn, before this interrupt. That used to be a real
        hazard the day a non-idempotent, ungated tool got added
        (replaying it would re-trigger its side effect for real).
        Fixed: _execute_tool() below wraps the actual tool invocation
        in a LangGraph @task, which checkpoints its result the first
        time it runs -- a replay returns that cached result instead of
        re-invoking the tool. Verified live (real interrupt/resume
        against the real Postgres checkpointer, an ungated tool called
        before a gated one in the same turn): the ungated tool executes
        exactly once across the full pause/resume cycle.
        """

        from langgraph.types import interrupt

        resume_payload = interrupt(
            {
                "execution_id": action.execution_id,
                "thread_id": action.thread_id,
                "conversation_event_id": action.conversation_event_id,
                "agent_id": action.agent_id,
                "action_type": action.action_type.value,
                "actor_type": action.actor_type.value,
                "tool_name": action.tool_name,
                "parameters": action.parameters,
                "reason": action.reason,
            }
        )

        if resume_payload.get("decision") != "approved":
            return ToolResult(
                tool_name=action.tool_name or "",
                success=False,
                content="",
                evidence=(),
                execution_metadata={"approval_decision": resume_payload.get("decision")},
                error="Action was not approved by a human reviewer.",
            )

        return ToolResult.from_dict(resume_payload["tool_result"])

    async def _execute_tool(
        self,
        *,
        handle: AgentExecutionHandle,
        action: AgentActionRequestDTO,
    ) -> ToolResult:
        """
        Execute one tool call while enforcing the agent lifecycle budget.

        The real invocation runs inside a LangGraph @task (see
        run_tool_task below, dispatched through _call_replay_safe) so
        that a LATER interrupt()/resume in the SAME agent turn -- which
        replays this whole node from the top, see
        _execute_gated_tool()'s docstring -- returns this call's
        checkpointed result instead of re-invoking the tool. Only
        tool_name/parameters (both plain, serializable types) are
        declared as the task's real arguments; it closes over
        self._tool_execution_service via a nested function rather than
        passing it as an argument, since @task's checkpointer needs to
        serialize declared inputs (a live service object holding a
        ToolRegistry is not serializable) -- verified this closure
        pattern doesn't affect replay-matching (LangGraph matches task
        calls by position/call-order within the node, the same way it
        matches interrupt() calls).
        """

        budget = handle.lifecycle.begin_tool_call()

        if not budget.allowed:
            return ToolResult(
                tool_name=action.tool_name or "",
                success=False,
                content="",
                evidence=(),
                execution_metadata={
                    "budget_exceeded": True,
                    "termination_reason": (
                        budget.reason.value if budget.reason is not None else None
                    ),
                },
                error="Tool-call execution budget exceeded.",
            )

        @langgraph_task
        async def run_tool_task(*, tool_name: str, parameters: dict) -> dict:
            result = await self._tool_execution_service.execute(
                tool_name=tool_name,
                parameters=parameters,
            )

            # Written INSIDE the @task body, deliberately -- not after
            # _call_replay_safe() returns below. A later interrupt()/
            # resume in the same turn replays run_tool_task's caller
            # from the top (see this method's own docstring), but the
            # checkpointed @task call itself returns its cached result
            # without re-running its body -- so a compliance write
            # placed here fires exactly once across a pause/resume
            # cycle, the same guarantee the tool invocation itself
            # already relies on. A write placed after this task call
            # instead would re-run on every replay and double- (or
            # triple-) count one real tool call.
            await self._record_tool_call_compliance(
                handle=handle,
                action=action,
                result=result,
            )

            return result.to_dict()

        result_dict = await _call_replay_safe(
            run_tool_task,
            tool_name=action.tool_name or "",
            parameters=action.parameters,
        )

        return ToolResult.from_dict(result_dict)

    async def _record_tool_call_compliance(
        self,
        *,
        handle: AgentExecutionHandle,
        action: AgentActionRequestDTO,
        result: ToolResult,
    ) -> None:
        """
        Compliance log: TOOL_CALL_EXECUTED for every tool call, plus
        RETRIEVAL_PERFORMED when the tool actually returned evidence
        (reuses ToolResultConverter -- the same RetrievedContentDTO
        conversion the reasoning-context path already applies to this
        result, not a second evidence shape).
        """

        context = handle.request.context

        if not context.request_id:
            # A resume()'d execution's AgentContextDTO is reconstructed
            # from LangGraph checkpoint state (see AgentExecutionResult
            # -- Executor.resume()) and may not carry request_id the
            # same way a fresh handle() call does (see
            # AgentContextDTO.request_id's own docstring) -- skip
            # rather than fail a real tool call over a missing
            # correlation id for what is still a known, narrow gap.
            return

        try:
            request_id = UUID(context.request_id)
        except ValueError:
            return

        await self._compliance_log.record_tool_call_executed(
            request_id=request_id,
            user_id=context.user_id,
            tenant_id=context.user_id,
            thread_id=context.thread_id,
            agent_id=action.agent_id,
            tool_name=action.tool_name or "",
            success=result.success,
        )

        # Gated on result.evidence specifically, not the converted
        # reasoning-context tuple -- ToolResultConverter falls back to
        # wrapping a tool's plain top-level content as one context
        # item when there's no explicit evidence, which would make
        # every successful non-retrieval tool call (e.g. a
        # send-email/slack action) misreported as a retrieval. Only an
        # explicit ToolEvidence list is a real retrieval signal.
        if result.success and result.evidence:
            await self._compliance_log.record_retrieval_performed(
                request_id=request_id,
                user_id=context.user_id,
                tenant_id=context.user_id,
                thread_id=context.thread_id,
                agent_id=action.agent_id,
                retrieved=ToolResultConverter.to_reasoning_context(result=result),
            )

    async def _delegate(
        self,
        *,
        handle: AgentExecutionHandle,
        action: AgentActionRequestDTO,
    ) -> object | None:
        """
        Delegate work through the collaboration bus.

        The parent execution owns the agent-hop budget.

        Delegation failures propagate to the execution layer. A budget
        denial is handled as a normal PARTIAL lifecycle termination.

        NOT wrapped in the same replay-safety @task fix as
        _execute_tool() (see there) -- deliberately, not an oversight.
        DELEGATE is confirmed unreachable in production today
        (AgentPolicyGuard.check_delegation() always denies: allow_
        delegation defaults False and agent_policies has no column for
        it -- see claude.md's CollaborationBus audit), so there is no
        live replay hazard to fix yet. It would also need a real
        serialization scheme first: CollaborationBus.send() returns a
        bare ``object`` (whatever the target agent's handle_message()
        produces, e.g. a pydantic AgentDecision), and a @task's
        checkpointed return value needs the same plain-dict treatment
        ToolResult got here -- inventing that for a type this method
        doesn't actually constrain would be guessing. Revisit
        alongside adding real allow_delegation support.
        """

        target_agent_id = action.target_agent_id

        if not target_agent_id:
            raise ValueError(
                "Agent delegation requires a target_agent_id.",
            )

        budget = handle.lifecycle.begin_agent_hop()

        if not budget.allowed:
            return None

        request = handle.request

        message = AgentMessageSchema(
            sender=action.agent_id,
            recipient=target_agent_id,
            capability=AgentDecisionType.DELEGATE.value,
            payload={
                "request": request,
                "parameters": action.parameters,
            },
        )

        return await self._collaboration_bus.send(
            message=message,
        )

    @staticmethod
    def _request_question(request: object) -> str:
        """
        Extract the current user question from the real AgentRequestDTO contract.

        AgentRequestDTO does not expose a top-level ``question`` attribute.
        The current question is represented by the latest USER message in the
        request conversation. If no USER message exists, fall back to the
        request instruction rather than inventing a separate DTO field.
        """

        conversation = getattr(request, "conversation", None)
        messages = getattr(conversation, "messages", ()) if conversation else ()

        for message in reversed(messages):
            role = getattr(message, "role", None)
            if (
                role is MessageRoleEnum.USER
                or getattr(role, "value", None) == MessageRoleEnum.USER.value
            ):
                return getattr(message, "content", "") or ""

        return getattr(request, "instruction", "") or ""

    async def _gate_final(
        self,
        *,
        handle: AgentExecutionHandle,
        result: AgentExecutionResult,
    ) -> tuple[AgentExecutionResult | None, AnswerEvaluationSummary | None]:
        """
        Evaluate a proposed FINAL answer against accumulated evidence.

        Returns one of:

        - (None, summary with verified=True): accept the FINAL result
          as-is.
        - (a new result, None): insufficient, and a retry produced a
          new result to continue on.
        - (a terminal result, summary with verified=False): insufficient
          and nothing left to improve it -- the step budget is
          exhausted, or the retry ended the execution before a new
          decision was handled -- or the execution had already ended
          when this FINAL arrived, so it was never accepted. The answer is replaced with
          UNVERIFIED_ANSWER_MESSAGE and the execution ends with
          QUALITY_GATE_EXHAUSTED (S5). The caller must return this
          result, not gate it again: its decision is still the rejected
          FINAL, so re-gating it would loop.

        A groundedness or relevance failure specifically triggers a
        structural corrective-retrieval retry (_force_corrective_retrieval):
        a real TOOL_CALL to "retriever" is forced before the next FINAL
        attempt, rather than just re-asking the same LLM with a note and
        no new information. Those are the only two dimensions where more
        evidence is actually the right remedy (an ungrounded or
        off-topic answer needs new material, not just a nudge); a
        correctness or citation failure (the only other ways
        is_sufficient can return False) falls back to the weak
        re-ask-with-feedback retry below, since forcing a retrieval
        wouldn't address either.
        """

        decision = result.decision
        answer = decision.final_response if decision is not None else None

        if not answer:
            return None, None

        if handle.lifecycle.state.status is not AgentExecutionStatus.RUNNING:
            # The runtime ended the execution (a budget ran out) after the
            # model proposed this FINAL but before accepting it, so its
            # text never became the response. It can't be accepted or
            # retried; the handle is closed.
            return self._reject_unverified(
                handle=handle,
                evaluation=None,
            )

        evidence = tuple(item.content for item in self._evidence_items(handle))

        evaluation = await self._answer_evaluator.evaluate(
            question=self._request_question(handle.request),
            answer=answer,
            evidence=evidence,
        )

        if self._answer_quality_policy.is_sufficient(evaluation):
            return None, AnswerEvaluationSummary(
                groundedness=evaluation.groundedness,
                relevance=evaluation.relevance,
            )

        step_budget = handle.lifecycle.begin_step()
        if not step_budget.allowed:
            return self._reject_unverified(
                handle=handle,
                evaluation=evaluation,
            )

        rejected_response = handle.lifecycle.state.partial_response

        missing_evidence = (
            self._answer_quality_policy.require_evidence
            and not evaluation.groundedness_detail.applicable
        )

        if missing_evidence:
            # A1: one corrective retrieval. If it can't run or finds
            # nothing, no answer can be grounded -- don't re-ask the
            # model to answer from its own knowledge.
            retried = await self._force_corrective_retrieval(
                handle=handle,
                evaluation=evaluation,
            )

            if retried is None:
                return self._reject_unverified(
                    handle=handle,
                    evaluation=evaluation,
                )

            next_result = retried
        else:
            next_result = await self._retry_insufficient(
                handle=handle,
                evaluation=evaluation,
            )

        if (
            handle.lifecycle.state.status is not AgentExecutionStatus.RUNNING
            and handle.lifecycle.state.partial_response == rejected_response
        ):
            # The retry ended the execution (a budget ran out, or the
            # reasoning call failed) before any new decision was handled:
            # the response is still the answer just rejected.
            return self._reject_unverified(
                handle=handle,
                evaluation=evaluation,
            )

        return next_result, None

    def _reject_unverified(
        self,
        *,
        handle: AgentExecutionHandle,
        evaluation: AnswerEvaluationResult | None,
    ) -> tuple[AgentExecutionResult, AnswerEvaluationSummary]:
        """
        End the execution with a fixed message in place of a FINAL
        answer that failed the quality gate: NO_SOURCES_ANSWER_MESSAGE
        (NO_EVIDENCE) when there is no evidence at all (A1), otherwise
        UNVERIFIED_ANSWER_MESSAGE (QUALITY_GATE_EXHAUSTED, S5).
        evaluation is None when the answer was never evaluated.
        """

        if self._evidence_items(handle):
            reason = TerminationReason.QUALITY_GATE_EXHAUSTED
            message = UNVERIFIED_ANSWER_MESSAGE
        else:
            reason = TerminationReason.NO_EVIDENCE
            message = NO_SOURCES_ANSWER_MESSAGE

        handle.lifecycle.partial(reason)
        handle.lifecycle.set_partial_response(message)

        return handle.terminal_result(), AnswerEvaluationSummary(
            groundedness=evaluation.groundedness if evaluation else None,
            relevance=evaluation.relevance if evaluation else None,
            verified=False,
        )

    async def _retry_insufficient(
        self,
        *,
        handle: AgentExecutionHandle,
        evaluation: AnswerEvaluationResult,
    ) -> AgentExecutionResult:
        """
        One retry after an insufficient FINAL: corrective retrieval when
        groundedness or relevance failed, otherwise (or when retrieval
        couldn't run) a re-ask with the evaluation as feedback.
        """

        groundedness_failed = (
            evaluation.groundedness_detail.applicable
            and evaluation.groundedness < self._answer_quality_policy.min_groundedness
        )
        relevance_failed = evaluation.relevance < self._answer_quality_policy.min_relevance

        if groundedness_failed or relevance_failed:
            retried = await self._force_corrective_retrieval(
                handle=handle,
                evaluation=evaluation,
            )

            if retried is not None:
                return retried

            # Corrective retrieval itself couldn't run (budget exhausted
            # or the tool call failed) -- fall through to the weak
            # retry below rather than giving up outright.

        handle.extend_reasoning_context(
            context=(
                RetrievedContentDTO(
                    source=RetrievalSourceEnum.MEMORY,
                    source_name="answer_evaluator",
                    content=(
                        f"Previous answer was insufficient "
                        f"(groundedness={evaluation.groundedness:.2f}, "
                        f"relevance={evaluation.relevance:.2f}, "
                        f"completeness={evaluation.completeness:.2f}). "
                        f"Provide additional evidence or a more complete answer."
                    ),
                    score=None,
                    metadata={"source_type": EVALUATION_FEEDBACK},
                ),
            ),
        )

        return await handle.reason()

    async def _force_corrective_retrieval(
        self,
        *,
        handle: AgentExecutionHandle,
        evaluation: AnswerEvaluationResult,
    ) -> AgentExecutionResult | None:
        """
        Force a real "retriever" TOOL_CALL before the next FINAL attempt.

        Deterministic, not another LLM guess: re-runs retrieval for the
        original question (broadened via a higher top_k) rather than
        asking the model to invent a "refined query" through another
        generation call -- structural correction, not more self-report.

        Returns the next reasoning result on success, or None if the
        retrieval itself couldn't be attempted/failed (budget exhausted,
        policy denial, tool error) or found no evidence -- callers fall
        back to the weak retry in that case, or, when evidence is
        required and there is none, to the "no sources" answer.
        Policy and budget checks: see _retrieve_evidence.
        """

        context = await self._retrieve_evidence(
            handle=handle,
            top_k=CORRECTIVE_RETRIEVAL_TOP_K,
        )

        if not context:
            # Retrieval couldn't run or found nothing new to ground an
            # answer in.
            return None

        if not self._record_reasoning_context(
            handle=handle,
            context=context,
        ):
            return handle.terminal_result()

        if not self._record_progress(
            handle=handle,
            context=context,
        ):
            return handle.terminal_result()

        handle.extend_reasoning_context(
            context=(
                RetrievedContentDTO(
                    source=RetrievalSourceEnum.MEMORY,
                    source_name="answer_evaluator",
                    content=(
                        f"Previous answer failed quality checks "
                        f"(groundedness={evaluation.groundedness:.2f}, "
                        f"relevance={evaluation.relevance:.2f}). Additional "
                        f"evidence was retrieved above for the same "
                        f"question -- use it to provide a better-grounded, "
                        f"more relevant answer, or state that the question "
                        f"cannot be answered from the available evidence."
                    ),
                    score=None,
                    metadata={"source_type": CORRECTIVE_RETRIEVAL_FEEDBACK},
                ),
            ),
        )

        return await handle.reason()

    async def seed_evidence(
        self,
        *,
        handle: AgentExecutionHandle,
    ) -> None:
        """
        Retrieve evidence for the latest user question into the
        handle's reasoning_context before its first reasoning call (A1),
        so the agent starts from sources instead of its own knowledge.

        Policy-checked and budgeted like any retriever call; does
        nothing when the agent may not use the retriever, the budget is
        spent, or nothing is found. Called by AgentExecutionNode.
        """

        context = await self._retrieve_evidence(
            handle=handle,
            top_k=SEED_RETRIEVAL_TOP_K,
        )

        if context:
            self._record_reasoning_context(
                handle=handle,
                context=context,
            )

    async def _retrieve_evidence(
        self,
        *,
        handle: AgentExecutionHandle,
        top_k: int,
    ) -> tuple[RetrievedContentDTO, ...] | None:
        """
        One system-initiated "retriever" call for the latest user
        question, checked against the agent's policy and tool-call
        budget. Returns the evidence found (possibly empty), or None when
        the call couldn't run or failed.

        Goes through AgentPolicyGuard.check_tool() like any other tool
        call (agents/runtime/execution.py checks the same way for an
        LLM-proposed TOOL_CALL) -- this is a system-initiated call, not
        the LLM's, but it still uses a real tool and must respect the
        same policy the agent is bound by.
        """

        permission = self._agent_policy_guard.check_tool(
            policy=handle.policy,
            tool_name="retriever",
        )

        if not permission.allowed:
            return None

        tool_budget = handle.lifecycle.begin_tool_call()

        if not tool_budget.allowed:
            return None

        try:
            tool_result = await self._tool_execution_service.execute(
                tool_name="retriever",
                parameters={
                    "query": self._request_question(handle.request),
                    "top_k": top_k,
                },
            )

        except ToolNotFoundError:
            # No "retriever" tool registered for this deployment/agent.
            return None

        if not tool_result.success:
            return None

        return tuple(
            item
            for item in ToolResultConverter.to_reasoning_context(result=tool_result)
            if item.content not in NON_EVIDENCE_CONTENT
        )

    @staticmethod
    def _evidence_items(
        handle: AgentExecutionHandle,
    ) -> tuple[RetrievedContentDTO, ...]:
        """
        The reasoning_context items an answer can be grounded in: all of
        them except the gate's own feedback notes and the retriever's
        "nothing found" results.
        """

        return tuple(
            item
            for item in handle.reasoning_context
            if not is_feedback(item) and item.content not in NON_EVIDENCE_CONTENT
        )

    @staticmethod
    def _record_progress(
        *,
        handle: AgentExecutionHandle,
        context: tuple[RetrievedContentDTO, ...],
    ) -> bool:
        """
        Record a deterministic progress identity for newly returned
        information.

        The continuation loop is already bounded by AgentLifecycle. This
        method only supplies the lifecycle with a stable identity for the
        information produced by the latest internal action.

        Equal information produces the same key, regardless of dictionary
        ordering or object representation. New information produces a new
        key and resets the consecutive no-progress counter.
        """

        payload = [
            {
                "content": item.content,
                "metadata": item.metadata or {},
                "score": item.score,
                "source": item.source.value if hasattr(item.source, "value") else str(item.source),
                "source_name": item.source_name,
            }
            for item in context
        ]

        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        progress_key = hashlib.sha256(
            serialized.encode("utf-8"),
        ).hexdigest()

        result = handle.lifecycle.record_progress(
            progress_key,
        )

        return result.allowed

    @staticmethod
    def _record_reasoning_context(
        *,
        handle: AgentExecutionHandle,
        context: tuple[RetrievedContentDTO, ...],
    ) -> bool:
        """
        Record converted evidence/context within lifecycle budgets.
        """

        if not context:
            return True

        count = len(context)
        state = handle.lifecycle.state
        budget = state.budget

        if state.evidence_count + count > budget.max_evidence_items:
            handle.lifecycle.partial(
                TerminationReason.PARTIAL_MAX_EVIDENCE_ITEMS,
            )
            return False

        if state.context_count + count > budget.max_context_items:
            handle.lifecycle.partial(
                TerminationReason.PARTIAL_MAX_CONTEXT_ITEMS,
            )
            return False

        evidence_budget = handle.lifecycle.record_evidence(
            count=count,
        )

        if not evidence_budget.allowed:
            return False

        context_budget = handle.lifecycle.record_context(
            count=count,
        )

        if not context_budget.allowed:
            return False

        handle.extend_reasoning_context(
            context=context,
        )

        return True

    @staticmethod
    def _delegation_to_reasoning_context(
        *,
        action: AgentActionRequestDTO,
        result: object,
    ) -> tuple[RetrievedContentDTO, ...]:
        """
        Convert delegated-agent output into reasoning context.

        Delegated-agent output is not retrieval evidence, so it is
        represented using the existing MEMORY retrieval source.
        """

        if result is None:
            return ()

        if isinstance(result, str):
            content = result
        else:
            content = str(result)

        if not content:
            return ()

        return (
            RetrievedContentDTO(
                source=RetrievalSourceEnum.MEMORY,
                source_name=action.target_agent_id or "delegated_agent",
                content=content,
                score=None,
                metadata={
                    "source_type": "agent_delegation",
                    "target_agent_id": action.target_agent_id,
                },
            ),
        )
