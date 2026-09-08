"""
Unit tests for the current LangGraph AgentExecutionNode boundary.

The graph node delegates agent-level execution to AgentExecution and only
maps the resulting AgentExecutionResult into graph-state updates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.execution.graph.nodes import AgentExecutionNode
from core.dto.agent import AgentRequestDTO
from core.dto.tool import ToolFileDTO
from core.enums import ExecutionStatusEnum
from tests.builders.agentic.agent import build_agent_context
from tests.builders.agentic.execution import build_graph_state
from tests.builders.agentic.planning import build_plan, build_step


def _build_result(
    *,
    status: ExecutionStatusEnum,
    retry_count: int = 0,
    error: str | None = None,
    decision: object | None = None,
    action: object | None = None,
    termination_reason: str | None = None,
) -> MagicMock:
    now = datetime.now(UTC)

    result = MagicMock()
    result.status = status
    result.retry_count = retry_count
    result.started_at = now
    result.completed_at = now
    result.error = error
    result.decision = decision
    result.action = action
    result.termination_reason = termination_reason

    return result


def _build_node(
    *,
    result: MagicMock,
) -> tuple[AgentExecutionNode, MagicMock, MagicMock, MagicMock]:
    """
    Build collaborators for the current AgentExecutionNode contract.

    AgentExecutionNode:
        start() -> handle
        handle.reason() -> initial result
        continuation_service.execute() -> continuation result
    """
    agent_execution = MagicMock()
    continuation_service = MagicMock()
    handle = MagicMock()

    handle.reason = AsyncMock(return_value=result)
    agent_execution.start = AsyncMock(return_value=handle)

    continuation_result = MagicMock()
    continuation_result.result = result
    continuation_result.action = getattr(result, "action", None)

    continuation_service.execute = AsyncMock(
        return_value=continuation_result,
    )

    node = AgentExecutionNode(
        agent_execution=agent_execution,
        continuation_service=continuation_service,
    )

    return node, agent_execution, continuation_service, handle


def _build_graph_state(*, plan, context=None):
    """
    build_graph_state in the existing test builders predates the
    reasoning_context graph field. Add the required field explicitly so
    these tests exercise the current node contract.
    """
    state = build_graph_state(
        plan=plan,
        **({"context": context} if context is not None else {}),
    )
    state["reasoning_context"] = ()
    return state


@pytest.mark.asyncio
async def test_execute_step_delegates_to_agent_execution_and_completes() -> None:
    step = build_step("step-a")
    execution_result = _build_result(
        status=ExecutionStatusEnum.COMPLETED,
    )

    node, agent_execution, continuation_service, handle = _build_node(
        result=execution_result,
    )

    graph_state = _build_graph_state(
        plan=build_plan(steps=(step,)),
    )

    result = await node(graph_state, step=step)

    agent_execution.start.assert_awaited_once_with(
        agent_id=step.agent,
        request=AgentRequestDTO(
            conversation=graph_state["conversation"],
            instruction=step.instruction,
            arguments=step.arguments,
            context=graph_state["context"],
        ),
        reasoning_context=(),
    )

    handle.reason.assert_awaited_once_with()

    continuation_service.execute.assert_awaited_once_with(
        handle=handle,
        initial_result=execution_result,
    )

    update = result["execution_state_updates"][0]

    assert update["step_id"] == step.id
    assert update["status"] is ExecutionStatusEnum.COMPLETED
    assert update["retry_count"] == 0
    assert update["started_at"] == execution_result.started_at
    assert update["completed_at"] == execution_result.completed_at
    assert update["error"] is None
    assert update["termination_reason"] is None


@pytest.mark.asyncio
async def test_execute_step_maps_failed_execution_result() -> None:
    step = build_step("step-a")
    execution_result = _build_result(
        status=ExecutionStatusEnum.FAILED,
        error="Non-retryable failure",
    )

    node, agent_execution, continuation_service, handle = _build_node(
        result=execution_result,
    )

    graph_state = _build_graph_state(
        plan=build_plan(steps=(step,)),
    )

    result = await node(graph_state, step=step)

    agent_execution.start.assert_awaited_once()
    handle.reason.assert_awaited_once_with()
    continuation_service.execute.assert_awaited_once_with(
        handle=handle,
        initial_result=execution_result,
    )

    update = result["execution_state_updates"][0]

    assert update["step_id"] == step.id
    assert update["status"] is ExecutionStatusEnum.FAILED
    assert update["retry_count"] == 0
    assert update["error"] == "Non-retryable failure"
    assert update["started_at"] == execution_result.started_at
    assert update["completed_at"] == execution_result.completed_at

    assert "agent_decision_updates" not in result
    assert "action" not in result


@pytest.mark.asyncio
async def test_execute_step_preserves_retry_count_from_agent_execution() -> None:
    step = build_step("step-a")
    execution_result = _build_result(
        status=ExecutionStatusEnum.COMPLETED,
        retry_count=1,
    )

    node, agent_execution, continuation_service, handle = _build_node(
        result=execution_result,
    )

    graph_state = _build_graph_state(
        plan=build_plan(steps=(step,)),
    )

    result = await node(graph_state, step=step)

    agent_execution.start.assert_awaited_once()
    handle.reason.assert_awaited_once_with()
    continuation_service.execute.assert_awaited_once_with(
        handle=handle,
        initial_result=execution_result,
    )

    update = result["execution_state_updates"][0]

    assert update["status"] is ExecutionStatusEnum.COMPLETED
    assert update["retry_count"] == 1


@pytest.mark.asyncio
async def test_execute_step_adds_agent_decision_update() -> None:
    step = build_step("step-a")
    decision = MagicMock(name="agent_decision")

    execution_result = _build_result(
        status=ExecutionStatusEnum.COMPLETED,
        decision=decision,
    )

    node, agent_execution, continuation_service, handle = _build_node(result=execution_result)

    graph_state = _build_graph_state(
        plan=build_plan(steps=(step,)),
    )

    result = await node(graph_state, step=step)

    assert result["agent_decision_updates"] == [
        {
            "step_id": step.id,
            "decision": decision,
        }
    ]


@pytest.mark.asyncio
async def test_execute_step_adds_action_to_graph_update() -> None:
    step = build_step("step-a")
    action = MagicMock(name="business_action")

    execution_result = _build_result(
        status=ExecutionStatusEnum.COMPLETED,
        action=action,
    )

    node, agent_execution, continuation_service, handle = _build_node(result=execution_result)

    graph_state = _build_graph_state(
        plan=build_plan(steps=(step,)),
    )

    result = await node(graph_state, step=step)

    assert result["action"] is action


@pytest.mark.asyncio
async def test_execute_step_passes_request_context_and_reasoning_context() -> None:
    step = build_step("step-a")

    uploaded_file = ToolFileDTO(
        filename="contract.pdf",
        content=b"contract content",
        content_type="application/pdf",
    )

    context = build_agent_context(
        uploaded_files=(uploaded_file,),
        metadata={"source": "chat"},
    )

    execution_result = _build_result(
        status=ExecutionStatusEnum.COMPLETED,
    )

    node, agent_execution, continuation_service, handle = _build_node(
        result=execution_result,
    )

    graph_state = _build_graph_state(
        plan=build_plan(steps=(step,)),
        context=context,
    )

    reasoning_context = (MagicMock(name="retrieved-content"),)
    graph_state["reasoning_context"] = reasoning_context

    await node(
        graph_state,
        step=step,
    )

    agent_execution.start.assert_awaited_once()

    handle.reason.assert_awaited_once_with()

    continuation_service.execute.assert_awaited_once_with(
        handle=handle,
        initial_result=execution_result,
    )

    request = agent_execution.start.await_args.kwargs["request"]

    actual_reasoning_context = agent_execution.start.await_args.kwargs["reasoning_context"]

    assert isinstance(request, AgentRequestDTO)
    assert request.conversation == graph_state["conversation"]
    assert request.instruction == step.instruction
    assert request.arguments == step.arguments
    assert request.context is context
    assert request.context.uploaded_files == (uploaded_file,)
    assert request.context.metadata == {
        "source": "chat",
    }

    assert actual_reasoning_context == (reasoning_context)
