"""
Planning domain models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum


class ExecutionStepResponseSchema(BaseModel):
    """
    Structured execution step returned by the LLM.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    id: str

    agent: AgentTypeEnum

    instruction: str
    depends_on: tuple[str, ...] = ()

    stage: int = 1

    arguments: dict[str, Any] = Field(
        default_factory=dict,
    )


class ExecutionPlanResponseSchema(BaseModel):
    """
    Structured execution plan returned by the LLM.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    intent: IntentEnum

    mode: ExecutionModeEnum

    steps: tuple[
        ExecutionStepResponseSchema,
        ...,
    ]

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )
