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

from langgraph.config import var_child_runnable_config
from langgraph.func import task as langgraph_task

from agentic.agents.runtime.execution import (
    AgentExecutionHandle,
    AgentExecutionResult,
)
from agentic.agents.runtime.lifecycle.termination import TerminationReason
from agentic.collaboration.bus import CollaborationBus
from agentic.decisions.decision import AgentDecisionType
from agentic.evaluation.answer import (
    AnswerEvaluationResult,
    AnswerEvaluator,
    AnswerQualityPolicy,
)
from agentic.policy.guard import AgentPolicyGuard
from agentic.tools.result import ToolResult
from agentic.tools.runtime.invocation import ToolExecutionService
from agentic.tools.runtime.result_converter import ToolResultConverter
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import ActionTypeEnum, MessageRoleEnum, RetrievalSourceEnum
from core.exceptions.registry import ToolNotFoundError
from core.models.message import AgentMessageSchema


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


@dataclass(slots=True, frozen=True)
class AgentContinuationResult:
    """
    Result of one complete agent continuation sequence.
    """

    result: AgentExecutionResult
    action: AgentActionRequestDTO | None = None
    tool_results: tuple[ToolResult, ...] = ()


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
    ) -> None:
        self._tool_execution_service = tool_execution_service
        self._collaboration_bus = collaboration_bus
        self._answer_evaluator = answer_evaluator
        self._answer_quality_policy = answer_quality_policy
        self._agent_policy_guard = agent_policy_guard

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
                gated = await self._gate_final(
                    handle=handle,
                    result=result,
                )
                if gated is not None:
                    result = gated
                    continue
                return AgentContinuationResult(
                    result=result,
                    action=result.action,
                    tool_results=tuple(tool_results),
                )

            return AgentContinuationResult(
                result=result,
                action=result.action,
                tool_results=tuple(tool_results),
            )

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
            return result.to_dict()

        result_dict = await _call_replay_safe(
            run_tool_task,
            tool_name=action.tool_name or "",
            parameters=action.parameters,
        )

        return ToolResult.from_dict(result_dict)

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
    ) -> AgentExecutionResult | None:
        """
        Evaluate a proposed FINAL answer against accumulated evidence.

        Returns a new result to continue on (insufficient + budget left),
        or None to accept the FINAL result as-is.

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
            return None

        evidence = tuple(item.content for item in handle.reasoning_context)

        evaluation = await self._answer_evaluator.evaluate(
            question=self._request_question(handle.request),
            answer=answer,
            evidence=evidence,
        )

        if self._answer_quality_policy.is_sufficient(evaluation):
            return None

        step_budget = handle.lifecycle.begin_step()
        if not step_budget.allowed:
            # An insufficient FINAL must never be accepted merely because the
            # continuation step budget is exhausted. Preserve the proposed
            # answer, but return the lifecycle's non-completed terminal result.
            return handle.terminal_result()

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
                    metadata={"source_type": "evaluation_feedback"},
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
        policy denial, tool error) -- callers fall back to the weak
        retry in that case rather than losing the turn entirely.

        Goes through AgentPolicyGuard.check_tool() like any other tool
        call (agents/runtime/execution.py checks the same way for an
        LLM-proposed TOOL_CALL) -- this is a system-initiated call, not
        a user's or the LLM's, but it still uses a real tool and must
        respect the same policy an agent would otherwise be bound by.
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

        query = self._request_question(handle.request)

        try:
            tool_result = await self._tool_execution_service.execute(
                tool_name="retriever",
                parameters={
                    "query": query,
                    "top_k": CORRECTIVE_RETRIEVAL_TOP_K,
                },
            )

        except ToolNotFoundError:
            # No "retriever" tool registered for this deployment/agent --
            # degrade to the weak retry rather than crashing the
            # continuation over a system-initiated corrective attempt.
            return None

        if not tool_result.success:
            return None

        context = ToolResultConverter.to_reasoning_context(
            result=tool_result,
        )

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
                    metadata={"source_type": "corrective_retrieval_feedback"},
                ),
            ),
        )

        return await handle.reason()

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
