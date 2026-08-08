"""
Runtime execution composition.

Creates the execution runtime.

Responsibilities:

- Create execution strategies
- Assemble the executor

No business logic belongs in this module.
"""

from __future__ import annotations

from src.execution.executor import Executor
from src.execution.hybrid import HybridExecutionStrategy
from src.execution.parallel import ParallelExecutionStrategy
from src.execution.sequential import SequentialExecutionStrategy
from src.runtime.containers import RegistryContainer


def create_executor(
    *,
    registries: RegistryContainer,
) -> Executor:
    """
    Create the execution runtime.
    """

    return Executor(
        agent_registry=registries.agent_registry,
        sequential_strategy=SequentialExecutionStrategy(),
        parallel_strategy=ParallelExecutionStrategy(),
        hybrid_strategy=HybridExecutionStrategy(),
    )
