"""
Execution runtime factory.
"""

from __future__ import annotations

from src.execution.config import ExecutionRetryPolicy, ExecutionTimeoutPolicy
from src.execution.executor import Executor
from src.execution.graph.builder import ExecutionGraphBuilder
from src.execution.graph.factory import ExecutionGraphFactory
from src.execution.retry import RetryClassifier
from src.execution.state import ExecutionStateAssembler
from src.runtime.containers import RegistryContainer


def create_executor(
    *,
    registries: RegistryContainer,
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
    )

    state_assembler = ExecutionStateAssembler()

    return Executor(
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=timeout_policy,
    )
