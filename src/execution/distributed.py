"""
Distributed execution strategy.

Reserved for future distributed execution support.
"""

from __future__ import annotations

from src.core.models.planning import ExecutionPlan
from src.execution.protocols import ExecutionStrategy, StepRunner


class DistributedExecutionStrategy(ExecutionStrategy):
    """
    Executes an execution plan using a distributed
    execution backend.

    This strategy is reserved for a future phase where
    execution may be delegated to external workers
    (for example, Celery, Ray, Temporal, or Kubernetes Jobs).
    """

    async def execute(
        self,
        *,
        plan: ExecutionPlan,
        step_runner: StepRunner,
    ) -> None:
        """
        Execute the supplied execution plan using a distributed
        execution backend.
        """

        raise NotImplementedError(
            "Distributed execution strategy is not implemented.",
        )
