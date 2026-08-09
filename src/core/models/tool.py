"""
Tool domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.enums import RetrievalSource


@dataclass(slots=True, frozen=True)
class RetrievedContent:
    """
    Content retrieved from a knowledge source.
    """

    source: RetrievalSource

    content: str

    score: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
