"""
Hybrid execution strategy.
"""

from __future__ import annotations

import asyncio
from itertools import groupby

from src.core.models.planning import ExecutionPlan
from src.execution.protocols import ExecutionStrategy, StepRunner


class HybridExecutionStrategy(ExecutionStrategy):
    """
    Executes execution stages sequentially while executing
    all steps within a stage in parallel.
    """

    async def execute(
        self,
        *,
        plan: ExecutionPlan,
        step_runner: StepRunner,
    ) -> None:
        """
        Execute a hybrid execution plan.
        """

        steps = sorted(
            plan.steps,
            key=lambda step: step.stage,
        )

        for _, stage_steps in groupby(
            steps,
            key=lambda step: step.stage,
        ):
            await asyncio.gather(
                *(
                    step_runner(
                        step=step,
                    )
                    for step in stage_steps
                ),
            )
