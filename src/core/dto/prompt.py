"""
Prompt domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.dto.agent import AgentRequestDTO
from src.core.dto.planning import Intent, PlanningRequestDTO
from src.core.dto.tool import RetrievedContentDTO


@dataclass(slots=True, frozen=True)
class AgentPromptRequestDTO:
    """
    Request used to build an agent prompt.
    """

    request: AgentRequestDTO

    context: tuple[
        RetrievedContentDTO,
        ...,
    ] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class PlanningPromptRequestDTO:
    """
    Request used to build a planning prompt.
    """

    request: PlanningRequestDTO

    intent: Intent

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
