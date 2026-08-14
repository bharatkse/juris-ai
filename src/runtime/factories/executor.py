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
from src.execution.strategies.hybrid import HybridExecutionStrategy
from src.execution.strategies.parallel import ParallelExecutionStrategy
from src.execution.strategies.sequential import SequentialExecutionStrategy
from src.runtime.containers import RegistryContainer


def create_executor(*, registries: RegistryContainer) -> Executor:
    return Executor(
        agent_registry=registries.agent_registry,
        sequential_strategy=SequentialExecutionStrategy(),
        parallel_strategy=ParallelExecutionStrategy(),
        hybrid_strategy=HybridExecutionStrategy(),
    )
