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
    """

    id: str

    agent: AgentTypeEnum

    instruction: str

    stage: int = 1

    arguments: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class ExecutionPlanDTO:
    """
    Execution plan produced by the planner.
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


@dataclass(slots=True, frozen=True)
class PlanningPromptRequestDTO:
    """
    Planning prompt request.
    """

    planning_request: PlanningRequestDTO

    intent: IntentEnum
