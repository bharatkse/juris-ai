"""
Unit tests for execution graph building.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langgraph.graph import END, START

from src.core.enums import ExecutionModeEnum, ExecutionStatusEnum
from src.execution.graph.builder import ExecutionGraphBuilder
from src.execution.graph.state import ExecutionStepUpdate
from tests.builders.execution import build_graph_state
from tests.builders.planning import build_plan, build_step


@pytest.mark.asyncio
async def test_build_creates_step_nodes(
    execution_graph_builder: ExecutionGraphBuilder,
) -> None:
    """
    It should create one graph node for every execution step.
    """

    plan = build_plan(
        steps=(
            build_step("step-a"),
            build_step("step-b"),
        ),
    )

    step_node = AsyncMock(
        return_value={},
    )

    graph = execution_graph_builder.build(
        plan=plan,
        step_node=step_node,
    )

    assert "step-a" in graph.nodes
    assert "step-b" in graph.nodes


def test_build_adds_start_edge_for_root_step(
    execution_graph_builder: ExecutionGraphBuilder,
) -> None:
    """
    It should connect a step without dependencies to START.
    """

    plan = build_plan(
        steps=(build_step("step-a"),),
    )

    step_node = AsyncMock(
        return_value={},
    )

    graph = execution_graph_builder.build(
        plan=plan,
        step_node=step_node,
    )

    assert (
        START,
        "step-a",
    ) in graph.edges


def test_build_adds_edge_for_single_dependency(
    execution_graph_builder: ExecutionGraphBuilder,
) -> None:
    """
    It should connect a dependent step to its single dependency.
    """

    plan = build_plan(
        steps=(
            build_step("step-a"),
            build_step(
                "step-b",
                depends_on=("step-a",),
            ),
        ),
    )

    step_node = AsyncMock(
        return_value={},
    )

    graph = execution_graph_builder.build(
        plan=plan,
        step_node=step_node,
    )

    assert (
        "step-a",
        "step-b",
    ) in graph.edges


@pytest.mark.asyncio
async def test_step_node_skips_when_any_dependency_failed(
    execution_graph_builder: ExecutionGraphBuilder,
) -> None:
    """
    It should skip a step when any dependency failed.
    """

    plan = build_plan(
        mode=ExecutionModeEnum.HYBRID,
        steps=(
            build_step("step-a"),
            build_step("step-b"),
            build_step(
                "step-c",
                depends_on=(
                    "step-a",
                    "step-b",
                ),
            ),
        ),
    )

    step_node = AsyncMock(
        return_value={},
    )

    graph = execution_graph_builder.build(
        plan=plan,
        step_node=step_node,
    )

    graph_state = build_graph_state(
        plan=plan,
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error=None,
            ),
            ExecutionStepUpdate(
                step_id="step-b",
                status=ExecutionStatusEnum.FAILED,
                retry_count=2,
                started_at=None,
                completed_at=None,
                error="Simulated failure.",
            ),
        ],
    )

    node = graph.nodes["step-c"].runnable

    result = await node.ainvoke(
        graph_state,
    )

    assert result["execution_state_updates"][0]["step_id"] == "step-c"

    assert result["execution_state_updates"][0]["status"] is ExecutionStatusEnum.SKIPPED

    step_node.assert_not_awaited()


def test_build_adds_end_edge_for_terminal_step(
    execution_graph_builder: ExecutionGraphBuilder,
) -> None:
    """
    It should connect a terminal step to END.
    """

    plan = build_plan(
        steps=(build_step("step-a"),),
    )

    step_node = AsyncMock(
        return_value={},
    )

    graph = execution_graph_builder.build(
        plan=plan,
        step_node=step_node,
    )

    assert (
        "step-a",
        END,
    ) in graph.edges


@pytest.mark.asyncio
async def test_step_node_skips_when_dependency_failed(
    execution_graph_builder: ExecutionGraphBuilder,
) -> None:
    """
    It should skip a step when one of its dependencies failed.
    """

    plan = build_plan(
        steps=(
            build_step("step-a"),
            build_step(
                "step-b",
                depends_on=("step-a",),
            ),
        ),
    )

    step_node = AsyncMock(
        return_value={},
    )

    graph = execution_graph_builder.build(
        plan=plan,
        step_node=step_node,
    )

    graph_state = build_graph_state(
        plan=plan,
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.FAILED,
                retry_count=2,
                started_at=None,
                completed_at=None,
                error="Simulated failure.",
            ),
        ],
    )

    node = graph.nodes["step-b"].runnable

    result = await node.ainvoke(
        graph_state,
    )

    assert result["execution_state_updates"][0]["step_id"] == "step-b"

    assert result["execution_state_updates"][0]["status"] is ExecutionStatusEnum.SKIPPED

    step_node.assert_not_awaited()


@pytest.mark.asyncio
async def test_step_node_executes_when_dependencies_completed(
    execution_graph_builder: ExecutionGraphBuilder,
) -> None:
    """
    It should execute the step node when all dependencies completed.
    """

    plan = build_plan(
        steps=(
            build_step("step-a"),
            build_step(
                "step-b",
                depends_on=("step-a",),
            ),
        ),
    )

    expected_result = {
        "execution_state_updates": [
            ExecutionStepUpdate(
                step_id="step-b",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error=None,
            ),
        ],
    }

    step_node = AsyncMock(
        return_value=expected_result,
    )

    graph = execution_graph_builder.build(
        plan=plan,
        step_node=step_node,
    )

    graph_state = build_graph_state(
        plan=plan,
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error=None,
            ),
        ],
    )

    node = graph.nodes["step-b"].runnable

    result = await node.ainvoke(
        graph_state,
    )

    assert result == expected_result

    step_node.assert_awaited_once()
