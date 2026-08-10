"""
Sequential execution strategy.
"""

from __future__ import annotations

from src.core.models.planning import ExecutionPlan
from src.execution.protocols import ExecutionStrategy, StepRunner


class SequentialExecutionStrategy(ExecutionStrategy):
    """
    Executes execution steps sequentially.
    """

    async def execute(
        self,
        *,
        plan: ExecutionPlan,
        step_runner: StepRunner,
    ) -> None:
        """
        Execute all execution steps sequentially.
        """

        for step in plan.steps:
            await step_runner(
                step=step,
            )
