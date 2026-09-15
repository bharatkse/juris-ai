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

    The final chunk contains the completed OrchestratorResponse --
    not a bare per-agent AgentResponse, which carries no usage/
    approval/guardrail/action info. ChatService.stream_chat()'s tail
    needs all of those (via _persist_assistant_response(), shared with
    chat()) to reach real parity with the non-streaming path.
    """

    content: str = ""

    is_final: bool = False

    response: OrchestratorResponse | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
