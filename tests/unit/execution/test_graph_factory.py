"""
Unit tests for execution graph factory.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.execution.config import ExecutionRetryPolicy
from src.execution.graph.factory import ExecutionGraphFactory
from src.execution.retry import RetryClassifier
from tests.builders.planning import build_plan


@patch(
    "src.execution.graph.factory.AgentExecutionNode",
)
def test_create_builds_agent_node_and_compiles_graph(
    mock_agent_execution_node: MagicMock, mock_checkpointer: MagicMock
) -> None:
    """
    It should create the agent execution node and pass it to the
    graph builder for compilation.
    """

    plan = build_plan()

    builder = MagicMock()
    agent_registry = MagicMock()

    retry_policy = ExecutionRetryPolicy(
        max_attempts=3,
    )

    retry_classifier = RetryClassifier()

    step_node = MagicMock()

    mock_agent_execution_node.return_value = step_node

    factory = ExecutionGraphFactory(
        builder=builder,
        agent_registry=agent_registry,
        retry_policy=retry_policy,
        retry_classifier=retry_classifier,
        checkpointer=mock_checkpointer,
    )

    compiled_graph = MagicMock()

    builder.compile.return_value = compiled_graph

    result = factory.create(
        plan=plan,
    )

    assert result is compiled_graph

    mock_agent_execution_node.assert_called_once_with(
        agent_registry=agent_registry,
        retry_policy=retry_policy,
        retry_classifier=retry_classifier,
    )

    builder.compile.assert_called_once_with(
        plan=plan,
        step_node=step_node,
        checkpointer=mock_checkpointer,
    )
