"""
Unit tests for ExecutionGraphFactory.

The factory owns dependency wiring. The graph builder owns compilation,
including attaching the configured checkpointer.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agentic.execution.config import ExecutionRetryPolicy
from agentic.execution.graph.factory import ExecutionGraphFactory
from tests.builders.agentic.planning import build_plan, build_step


def test_create_builds_agent_node_and_compiles_graph() -> None:
    plan = build_plan(
        steps=(build_step("step-a"),),
    )

    builder = MagicMock()
    compiled_graph = MagicMock(name="compiled_graph")
    builder.compile.return_value = compiled_graph

    agent_registry = MagicMock()
    retry_policy = ExecutionRetryPolicy(max_attempts=3)
    retry_classifier = MagicMock()
    checkpointer = MagicMock()

    agent_policy_provider = MagicMock()
    agent_policy_guard = MagicMock()
    tool_execution_service = MagicMock()
    collaboration_bus = MagicMock()
    answer_evaluator = MagicMock()
    answer_quality_policy = MagicMock()

    factory = ExecutionGraphFactory(
        builder=builder,
        agent_registry=agent_registry,
        retry_policy=retry_policy,
        retry_classifier=retry_classifier,
        checkpointer=checkpointer,
        agent_policy_provider=agent_policy_provider,
        agent_policy_guard=agent_policy_guard,
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    )

    with (
        patch("agentic.execution.graph.factory.AgentExecution") as agent_execution_cls,
        patch(
            "agentic.execution.graph.factory.AgentContinuationService"
        ) as continuation_service_cls,
        patch("agentic.execution.graph.factory.AgentExecutionNode") as node_cls,
    ):
        agent_execution = MagicMock(name="agent_execution")
        continuation_service = MagicMock(name="continuation_service")
        step_node = MagicMock(name="step_node")

        agent_execution_cls.return_value = agent_execution
        continuation_service_cls.return_value = continuation_service
        node_cls.return_value = step_node

        result = factory.create(plan=plan)

    assert result is compiled_graph

    agent_execution_cls.assert_called_once()
    agent_execution_kwargs = agent_execution_cls.call_args.kwargs

    assert agent_execution_kwargs["agent_registry"] is agent_registry
    assert agent_execution_kwargs["retry_policy"] is retry_policy
    assert agent_execution_kwargs["retry_classifier"] is retry_classifier
    assert agent_execution_kwargs["agent_policy_provider"] is agent_policy_provider
    assert agent_execution_kwargs["agent_policy_guard"] is agent_policy_guard

    continuation_service_cls.assert_called_once_with(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=agent_policy_guard,
    )

    node_cls.assert_called_once_with(
        agent_execution=agent_execution,
        continuation_service=continuation_service,
    )

    builder.compile.assert_called_once_with(
        plan=plan,
        step_node=step_node,
        checkpointer=checkpointer,
    )
