"""
Sequential execution strategy.
"""

from __future__ import annotations

from src.core.dto.planning import ExecutionPlanDTO
from src.execution.protocols import ExecutionStrategy, StepRunner


class SequentialExecutionStrategy(ExecutionStrategy):
    """
    Executes execution steps sequentially.
    """

    async def execute(
        self,
        *,
        plan: ExecutionPlanDTO,
        step_runner: StepRunner,
    ) -> None:
        """
        Execute all execution steps sequentially.
        """

        for step in plan.steps:
            await step_runner(
                step=step,
            )
