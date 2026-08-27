"""
Prompt domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.dto.agent import AgentRequestDTO
from core.dto.tool import RetrievedContentDTO


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
