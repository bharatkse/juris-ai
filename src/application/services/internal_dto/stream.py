"""
Chat service streaming models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentic.orchestration.schemas.response import OrchestratorResponse


@dataclass(
    frozen=True,
    slots=True,
)
class ChatStreamChunkDTO:
    """
    Chunk returned while streaming a chat response.

    The final chunk contains the completed AgentResponse.
    """

    content: str = ""

    is_final: bool = False

    response: OrchestratorResponse | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
