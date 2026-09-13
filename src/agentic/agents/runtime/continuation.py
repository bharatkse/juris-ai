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
from core.enums import MessageRoleEnum, RetrievalSourceEnum
from core.exceptions.registry import ToolNotFoundError
from core.models.message import AgentMessageSchema

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

    async def _execute_tool(
        self,
        *,
        handle: AgentExecutionHandle,
        action: AgentActionRequestDTO,
    ) -> ToolResult:
        """
        Execute one tool call while enforcing the agent lifecycle budget.
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

        return await self._tool_execution_service.execute(
            tool_name=action.tool_name or "",
            parameters=action.parameters,
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
