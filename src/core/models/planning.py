"""
Planning domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.enums import AgentType, ExecutionMode, Intent
from src.core.models.conversation import Conversation


@dataclass(slots=True, frozen=True)
class PlanningRequest:
    """
    Planner request.
    """

    conversation: Conversation

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class ExecutionStep:
    """
    Single execution step.
    """

    id: str

    agent: AgentType

    instruction: str

    stage: int = 1

    arguments: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class ExecutionPlan:
    """
    Execution plan produced by the planner.
    """

    intent: Intent

    mode: ExecutionMode

    steps: tuple[
        ExecutionStep,
        ...,
    ]

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class PlanningResponse:
    """
    Planner response.
    """

    plan: ExecutionPlan


@dataclass(slots=True, frozen=True)
class PlanningPromptRequest:
    """
    Planning prompt request.
    """

    planning_request: PlanningRequest

    intent: Intent
