"""
Execution runtime factory.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver

from agentic.agents.runtime.retry import RetryClassifier
from agentic.collaboration.bus import CollaborationBus
from agentic.execution.config import (
    ExecutionRetryPolicy,
    ExecutionTimeoutPolicy,
)
from agentic.execution.executor import Executor
from agentic.execution.graph.builder import ExecutionGraphBuilder
from agentic.execution.graph.factory import ExecutionGraphFactory
from agentic.execution.state import ExecutionStateAssembler
from agentic.policy.agent_policy import StaticAgentPolicyProvider
from agentic.policy.config import AGENT_POLICIES
from agentic.policy.guard import AgentPolicyGuard
from agentic.policy.tool_permission import ToolPermissionGuard
from agentic.tools.runtime.invocation import ToolExecutionService
from wiring.containers import RegistryContainer


def create_executor(
    *,
    registries: RegistryContainer,
    collaboration_bus: CollaborationBus,
    checkpointer: BaseCheckpointSaver,
) -> Executor:
    """
    Create the configured execution runtime.
    """
    policy_provider = StaticAgentPolicyProvider(
        policies=AGENT_POLICIES,
    )

    policy_guard = AgentPolicyGuard(
        tool_permission_guard=ToolPermissionGuard(),
    )

    retry_policy = ExecutionRetryPolicy()
    retry_classifier = RetryClassifier()
    timeout_policy = ExecutionTimeoutPolicy()

    graph_builder = ExecutionGraphBuilder()

    tool_execution_service = ToolExecutionService(
        tool_registry=registries.tool_registry,
    )

    graph_factory = ExecutionGraphFactory(
        builder=graph_builder,
        agent_registry=registries.agent_registry,
        agent_policy_provider=policy_provider,
        agent_policy_guard=policy_guard,
        retry_policy=retry_policy,
        retry_classifier=retry_classifier,
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        checkpointer=checkpointer,
    )

    state_assembler = ExecutionStateAssembler()

    return Executor(
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=timeout_policy,
    )
