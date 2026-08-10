"""
Execution result models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.execution.state import ExecutionState


class ExecutionResult(BaseModel):
    """
    Result produced by an execution session.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    state: ExecutionState

    artifacts: dict[str, Any] = Field(
        default_factory=dict,
    )
