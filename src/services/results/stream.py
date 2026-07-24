"""
Chat streaming result models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class ChatStreamChunk:
    """
    Chunk returned by ChatService while streaming.

    This is the service-layer streaming contract.
    """

    content: str = ""

    is_final: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
