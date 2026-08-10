"""
Prompt domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.models.planning import Intent, PlanningRequest
from core.models.tool import RetrievedContent
from src.agents.models import AgentRequest


@dataclass(slots=True, frozen=True)
class AgentPromptRequest:
    """
    Request used to build an agent prompt.
    """

    request: AgentRequest

    context: tuple[
        RetrievedContent,
        ...,
    ] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class PlanningPromptRequest:
    """
    Request used to build a planning prompt.
    """

    request: PlanningRequest

    intent: Intent

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
