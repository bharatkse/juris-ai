"""
LangGraph execution nodes.

This module contains thin adapters between LangGraph execution state
and the agent execution service.

AgentExecution owns agent-level execution logic.

AgentExecutionNode only:
    1. reads graph state
    2. builds AgentRequestDTO
    3. starts AgentExecution
    4. invokes the request-scoped execution handle
    5. invokes AgentContinuationService for internal tool continuation
    6. converts the final AgentExecutionResult into graph updates
    7. for a streaming session's FINAL step only, also emits the
       streamed answer via LangGraph's custom stream channel -- pure
       side channel, never alters point 6's return value
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.config import get_stream_writer

from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.decisions.decision import AgentDecisionType
from agentic.evaluation.answer import AnswerEvaluationSummary
from agentic.execution.aggregation.mapper import AgentResponseMapper
from agentic.execution.graph.state import (
    AgentDecisionUpdate,
    ExecutionArtifactUpdate,
    ExecutionGraphState,
    ExecutionStepUpdate,
)
from core.dto.agent import AgentRequestDTO
from core.dto.planning import ExecutionStepDTO

if TYPE_CHECKING:
    from agentic.agents.runtime.execution import (
        AgentExecution,
        AgentExecutionHandle,
        AgentExecutionResult,
    )


class AgentExecutionNode:
    """
    Thin LangGraph adapter for one agent execution.

    This class intentionally contains no:

        - retry logic
        - budget logic
        - lifecycle logic
        - decision validation
        - tool execution
        - agent delegation
        - planning
        - agent reasoning

    Those responsibilities belong to AgentExecution,
    AgentContinuationService, or the appropriate execution boundary.
    """

    def __init__(
        self,
        *,
        agent_execution: AgentExecution,
        continuation_service: AgentContinuationService,
    ) -> None:
        self._agent_execution = agent_execution
        self._continuation_service = continuation_service

    async def __call__(
        self,
        state: ExecutionGraphState,
        *,
        step: ExecutionStepDTO,
    ) -> dict[str, Any]:
        """
        Execute one agent step.

        LangGraph-specific information stays in this adapter.
        """

        request = self._build_agent_request(
            state=state,
            step=step,
        )

        handle = await self._agent_execution.start(
            agent_id=step.agent,
            request=request,
            reasoning_context=tuple(
                state["reasoning_context"],
            ),
        )

        initial_result = await handle.reason()

        continuation_result = await self._continuation_service.execute(
            handle=handle,
            initial_result=initial_result,
        )

        if state.get(
            "streaming",
            False,
        ):
            await self._stream_final_answer_if_reached(
                handle=handle,
                result=continuation_result.result,
            )

        return self._to_graph_update(
            handle=handle,
            result=continuation_result.result,
            action=continuation_result.action,
            evaluation_summary=continuation_result.evaluation_summary,
            step=step,
        )

    @staticmethod
    async def _stream_final_answer_if_reached(
        *,
        handle: AgentExecutionHandle,
        result: AgentExecutionResult,
    ) -> None:
        """
        Emit the FINAL step's answer text via LangGraph's custom
        stream channel (get_stream_writer()) -- purely additive: the
        caller's graph-state return value (_to_graph_update(), built
        from the same `result` either way) is completely unaffected by
        whether this runs.

        Only fires for a FINAL decision -- a step that resolves to
        TOOL_CALL/DELEGATE/NEED_INPUT/FAIL never streams, whether or
        not this is a streaming session. In a multi-step plan this
        means at most one step ever streams: the one that reaches
        FINAL.

        Callers must already have confirmed this is a streaming
        session (state["streaming"]) before calling this -- checked
        once, by __call__ above, not repeated here.
        """

        if result.decision is None or result.decision.decision_type is not AgentDecisionType.FINAL:
            return

        writer = get_stream_writer()

        async for chunk in handle.stream_final_answer():
            writer(chunk)

    @staticmethod
    def _build_agent_request(
        *,
        state: ExecutionGraphState,
        step: ExecutionStepDTO,
    ) -> AgentRequestDTO:
        """
        Convert graph state and execution-plan step into
        the agent-facing request.

        `step.id` deliberately does not enter AgentRequestDTO.

        The step ID belongs to workflow execution and remains
        owned by the graph layer.
        """

        return AgentRequestDTO(
            conversation=state["conversation"],
            instruction=step.instruction,
            arguments=step.arguments,
            context=state["context"],
        )

    @staticmethod
    def _to_graph_update(
        *,
        handle: AgentExecutionHandle,
        result: AgentExecutionResult,
        action: Any | None,
        evaluation_summary: AnswerEvaluationSummary | None,
        step: ExecutionStepDTO,
    ) -> dict[str, Any]:
        """
        Convert an AgentExecutionResult into LangGraph state updates.

        Graph-specific step identity is added here rather than leaking
        it into AgentExecution.
        """

        update: dict[str, Any] = {
            "execution_state_updates": [
                ExecutionStepUpdate(
                    step_id=step.id,
                    status=result.status,
                    retry_count=result.retry_count,
                    started_at=result.started_at,
                    completed_at=result.completed_at,
                    error=result.error,
                    termination_reason=result.termination_reason,
                ),
            ],
        }

        if result.decision is not None:
            update["agent_decision_updates"] = [
                AgentDecisionUpdate(
                    step_id=step.id,
                    decision=result.decision,
                ),
            ]

            if result.decision.decision_type is AgentDecisionType.FINAL:
                mapper = AgentResponseMapper(agent_name=handle.agent_id)

                response = mapper.map(
                    state=handle.lifecycle.state,
                    execution_id=handle.request.context.execution_id,
                    context=handle.reasoning_context,
                    evaluation_summary=evaluation_summary,
                )

                update["memory_updates"] = [
                    ExecutionArtifactUpdate(
                        key=step.id,
                        value=response,
                    ),
                ]

        if action is not None:
            update["action"] = action

        return update
