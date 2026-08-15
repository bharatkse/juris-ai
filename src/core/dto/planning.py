"""
Planning domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from src.core.schemas.conversation import ConversationMessageSchema


@dataclass(slots=True, frozen=True)
class PlanningRequestDTO:
    """
    Planner request.
    """

    message: str

    history: tuple[ConversationMessageSchema, ...] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class ExecutionStepDTO:
    """
    Single execution step.

    A step describes what the executor should dispatch.
    It does not contain runtime execution state.

    Attributes:
        id:
            Stable identifier for the step within the plan.

        agent:
            Agent responsible for reasoning for this step.

        instruction:
            Planner-generated instruction for the agent.

        depends_on:
            IDs of steps that must complete before this step
            becomes eligible for execution.

            This is the authoritative execution dependency
            relationship.

        stage:
            Planner-level grouping metadata.

            Stage is not an execution dependency mechanism.
            Execution dependencies must be represented using
            depends_on.

        arguments:
            Structured arguments supplied to the agent.
    """

    id: str

    agent: AgentTypeEnum

    instruction: str

    depends_on: tuple[str, ...] = ()

    stage: int = 1

    arguments: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class ExecutionPlanDTO:
    """
    Execution plan produced by the planner.

    The plan is an immutable description of what should be
    executed.

    Runtime execution state does not belong to this DTO.
    """

    intent: IntentEnum

    mode: ExecutionModeEnum

    steps: tuple[
        ExecutionStepDTO,
        ...,
    ]

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class PlanningResponseDTO:
    """
    Planner response.
    """

    plan: ExecutionPlanDTO
