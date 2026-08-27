"""
Unit tests for execution session.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.execution.config import ExecutionTimeoutPolicy
from agentic.execution.schemas.memory import ExecutionMemorySchema
from agentic.execution.schemas.state import ExecutionStateSchema
from agentic.execution.session import ExecutionSession
from core.enums import ExecutionStatusEnum
from core.exceptions.execution import ExecutionError
from tests.builders.agentic.agent import build_agent_context
from tests.builders.agentic.execution import build_graph_state
from tests.builders.agentic.planning import build_plan
from tests.builders.application.conversation import build_conversation
from tests.helpers.identifiers import unknown_request_id


@pytest.mark.asyncio
async def test_execute_session(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should create the execution graph, invoke it, assemble the
    execution state and return the execution result.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    plan = build_plan()
    context = build_agent_context()

    graph_state = build_graph_state(
        request_id=request_id,
        plan=plan,
    )

    graph = MagicMock()

    graph.ainvoke = AsyncMock(
        return_value=graph_state,
    )

    graph_factory = MagicMock()

    graph_factory.create.return_value = graph

    state = ExecutionStateSchema(
        request_id=request_id,
        status=ExecutionStatusEnum.COMPLETED,
    )

    memory = ExecutionMemorySchema(
        artifacts={
            "step-a.response": "Executed A",
        },
    )

    state_assembler = MagicMock()

    state_assembler.assemble_state.return_value = state
    state_assembler.assemble_memory.return_value = memory

    # This test does not produce an action.
    state_assembler.assemble_action.return_value = None

    # ActionWorkflowService.prepare() is async and must return
    # a concrete preparation result, not an AsyncMock.
    preparation_result = MagicMock()

    preparation_result.action = None
    preparation_result.approval = None

    mock_action_workflow_service.prepare = AsyncMock(
        return_value=preparation_result,
    )

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(),
        action_workflow_service=mock_action_workflow_service,
    )

    result = await session.execute()

    graph_factory.create.assert_called_once_with(
        plan=plan,
    )

    graph.ainvoke.assert_awaited_once()

    state_assembler.assemble_state.assert_called_once_with(
        graph_state=graph_state,
    )

    state_assembler.assemble_memory.assert_called_once_with(
        graph_state=graph_state,
    )

    state_assembler.assemble_action.assert_called_once_with(
        graph_state=graph_state,
    )

    # Since no action was produced, ActionWorkflowService.prepare()
    # should not be called.
    mock_action_workflow_service.prepare.assert_not_awaited()

    assert result.state is state

    assert result.artifacts == {
        "step-a.response": "Executed A",
    }

    assert result.action is None
    assert result.approval is None


@pytest.mark.asyncio
async def test_execute_session_propagates_graph_execution_failure(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should propagate a graph execution failure.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    context = build_agent_context()
    plan = build_plan()

    graph = MagicMock()

    graph.ainvoke = AsyncMock(
        side_effect=RuntimeError(
            "Graph execution failed.",
        ),
    )

    graph_factory = MagicMock()

    graph_factory.create.return_value = graph

    state_assembler = MagicMock()

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(),
        action_workflow_service=mock_action_workflow_service,
    )

    with pytest.raises(
        RuntimeError,
        match="Graph execution failed.",
    ):
        await session.execute()

    graph_factory.create.assert_called_once_with(
        plan=plan,
    )

    graph.ainvoke.assert_awaited_once()

    state_assembler.assemble_state.assert_not_called()
    state_assembler.assemble_memory.assert_not_called()


@pytest.mark.asyncio
async def test_execute_session_times_out(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should raise a timeout when graph execution exceeds the
    configured execution timeout.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    context = build_agent_context()
    plan = build_plan()

    graph = MagicMock()

    async def slow_invoke(
        *args,
        **kwargs,
    ):
        await asyncio.sleep(0.1)

    graph.ainvoke = slow_invoke

    graph_factory = MagicMock()

    graph_factory.create.return_value = graph

    state_assembler = MagicMock()

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(
            timeout_seconds=0.01,
        ),
        action_workflow_service=mock_action_workflow_service,
    )

    with pytest.raises(
        ExecutionError,
        match="Execution timed out after 0.01 seconds.",
    ):
        await session.execute()

    graph_factory.create.assert_called_once_with(
        plan=plan,
    )

    state_assembler.assemble_state.assert_not_called()
    state_assembler.assemble_memory.assert_not_called()
