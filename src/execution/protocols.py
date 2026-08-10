"""
Execution runtime protocols.

Defines shared contracts used by the execution module.

These protocols decouple the Executor from execution strategies,
making each component independently testable.
"""

from __future__ import annotations

from typing import Protocol

from src.core.models.message import AgentMessage
from src.core.models.planning import ExecutionPlan, ExecutionStep


class StepRunner(Protocol):
    """
    Executes a single execution step.

    Implemented by:
        Executor._run_step()
    """

    async def __call__(
        self,
        *,
        step: ExecutionStep,
    ) -> None: ...


class ExecutionStrategy(Protocol):
    """
    Execution strategy contract.

    Implemented by:
        SequentialExecutionStrategy
        ParallelExecutionStrategy
        HybridExecutionStrategy
        DistributedExecutionStrategy
    """

    async def execute(
        self,
        *,
        plan: ExecutionPlan,
        step_runner: StepRunner,
    ) -> None: ...


class AgentMessageHandler(Protocol):
    """
    Handles inter-agent collaboration requests.
    """

    async def handle_message(
        self,
        *,
        message: AgentMessage,
    ) -> object: ...
