"""
Unit tests for execution session.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.dto.agent import AgentContextDTO
from src.core.enums import ExecutionStatusEnum
from src.core.exceptions.execution import ExecutionError
from src.execution.config import ExecutionTimeoutPolicy
from src.execution.schemas.memory import ExecutionMemorySchema
from src.execution.schemas.state import ExecutionStateSchema
from src.execution.session import ExecutionSession
from tests.builders.conversation import build_conversation
from tests.builders.execution import build_graph_state
from tests.builders.planning import build_plan
from tests.helpers.identifiers import unknown_request_id


@pytest.mark.asyncio
async def test_execute_session() -> None:
    """
    It should create the execution graph, invoke it, assemble the
    execution state and return the execution result.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    plan = build_plan()
    context = AgentContextDTO()
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

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(),
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

    assert result.state is state

    assert result.artifacts == {
        "step-a.response": "Executed A",
    }


@pytest.mark.asyncio
async def test_execute_session_propagates_graph_execution_failure() -> None:
    """
    It should propagate a graph execution failure.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    context = AgentContextDTO()
    plan = build_plan()

    graph = MagicMock()
    graph.ainvoke = AsyncMock(
        side_effect=RuntimeError("Graph execution failed."),
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
async def test_execute_session_times_out() -> None:
    """
    It should raise a timeout when graph execution exceeds the
    configured execution timeout.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    context = AgentContextDTO()
    plan = build_plan()

    graph = MagicMock()

    async def slow_invoke(*args, **kwargs):
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
