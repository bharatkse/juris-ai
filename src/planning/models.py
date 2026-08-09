"""
Planning domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.core.models.conversation import Conversation


class Intent(StrEnum):
    """
    Supported planning intents.
    """

    GENERAL = "general"

    LEGAL_RESEARCH = "legal_research"

    CONTRACT_REVIEW = "contract_review"

    CONTRACT_ANALYSIS = "contract_analysis"

    CLAUSE_EXTRACTION = "clause_extraction"

    RISK_ANALYSIS = "risk_analysis"


class AgentType(StrEnum):
    """
    Supported agent types.
    """

    LEGAL = "legal"

    CONTRACT = "contract"


class ExecutionMode(StrEnum):
    """
    Supported execution strategies.
    """

    SEQUENTIAL = "sequential"

    PARALLEL = "parallel"

    HYBRID = "hybrid"


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
