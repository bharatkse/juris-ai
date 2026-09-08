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

from dataclasses import dataclass

from agentic.agents.runtime.execution import (
    AgentExecutionHandle,
    AgentExecutionResult,
)
from agentic.agents.runtime.lifecycle.termination import TerminationReason
from agentic.collaboration.bus import CollaborationBus
from agentic.decisions.decision import AgentDecisionType
from agentic.tools.result import ToolResult
from agentic.tools.runtime.invocation import ToolExecutionService
from agentic.tools.runtime.result_converter import ToolResultConverter
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import RetrievalSourceEnum
from core.models.message import AgentMessageSchema


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
    ) -> None:
        self._tool_execution_service = tool_execution_service
        self._collaboration_bus = collaboration_bus

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

                tool_result = await self._execute_tool(
                    handle=handle,
                    action=action,
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

                result = await handle.reason()
                continue

            if decision.decision_type is AgentDecisionType.DELEGATE:
                action = result.action

                if action is None or not action.is_agent_call:
                    return AgentContinuationResult(
                        result=result,
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

                result = await handle.reason()
                continue

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

        handle.lifecycle.record_evidence(count=count)
        handle.lifecycle.record_context(count=count)

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
