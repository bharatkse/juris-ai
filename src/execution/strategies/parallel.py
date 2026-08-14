"""
Parallel execution strategy.
"""

from __future__ import annotations

import asyncio

from src.core.dto.planning import ExecutionPlanDTO
from src.execution.protocols import ExecutionStrategy, StepRunner


class ParallelExecutionStrategy(ExecutionStrategy):
    """
    Executes all execution steps concurrently.
    """

    async def execute(
        self,
        *,
        plan: ExecutionPlanDTO,
        step_runner: StepRunner,
    ) -> None:
        """
        Execute all execution steps in parallel.
        """

        await asyncio.gather(
            *(
                step_runner(
                    step=step,
                )
                for step in plan.steps
            ),
        )
