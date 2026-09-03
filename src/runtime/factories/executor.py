"""
Execution runtime factory.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver

from agentic.execution.config import ExecutionRetryPolicy, ExecutionTimeoutPolicy
from agentic.execution.executor import Executor
from agentic.execution.graph.builder import ExecutionGraphBuilder
from agentic.execution.graph.factory import ExecutionGraphFactory
from agentic.execution.retry import RetryClassifier
from agentic.execution.state import ExecutionStateAssembler
from runtime.containers import RegistryContainer


def create_executor(
    *,
    registries: RegistryContainer,
    checkpointer: BaseCheckpointSaver,
) -> Executor:
    """
    Create the configured execution runtime.
    """

    retry_policy = ExecutionRetryPolicy()
    retry_classifier = RetryClassifier()
    timeout_policy = ExecutionTimeoutPolicy()

    graph_builder = ExecutionGraphBuilder()

    graph_factory = ExecutionGraphFactory(
        builder=graph_builder,
        agent_registry=registries.agent_registry,
        retry_policy=retry_policy,
        retry_classifier=retry_classifier,
        checkpointer=checkpointer,
    )

    state_assembler = ExecutionStateAssembler()

    return Executor(
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=timeout_policy,
    )
