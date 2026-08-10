"""
Execution runtime state.

Represents mutable runtime state while executing an ExecutionPlan.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import ExecutionStatus


class StepExecutionState(BaseModel):
    """
    Runtime state for a single execution step.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    step_id: str

    status: ExecutionStatus = ExecutionStatus.PENDING

    started_at: datetime | None = None

    completed_at: datetime | None = None

    error: str | None = None


class ExecutionState(BaseModel):
    """
    Mutable runtime execution state.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    request_id: UUID

    status: ExecutionStatus = ExecutionStatus.PENDING

    hop_count: int = 0

    retry_count: int = 0

    steps: dict[str, StepExecutionState] = Field(
        default_factory=dict,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    def register_step(
        self,
        *,
        step_id: str,
    ) -> None:
        """
        Register a step before execution begins.
        """

        self.steps[step_id] = StepExecutionState(
            step_id=step_id,
        )

    def start_step(
        self,
        *,
        step_id: str,
    ) -> None:
        """
        Mark a step as running.
        """

        step = self.steps[step_id]

        step.status = ExecutionStatus.RUNNING
        step.started_at = datetime.now(UTC)

    def complete_step(
        self,
        *,
        step_id: str,
    ) -> None:
        """
        Mark a step as completed.
        """

        step = self.steps[step_id]

        step.status = ExecutionStatus.COMPLETED
        step.completed_at = datetime.now(UTC)

    def fail_step(
        self,
        *,
        step_id: str,
        error: str,
    ) -> None:
        """
        Mark a step as failed.
        """

        step = self.steps[step_id]

        step.status = ExecutionStatus.FAILED
        step.completed_at = datetime.now(UTC)
        step.error = error
