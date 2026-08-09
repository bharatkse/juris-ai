"""
Language model generation models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.models.message import Message


@dataclass(slots=True, frozen=True)
class GenerateRequest:
    """
    Language model generation request.
    """

    messages: tuple[Message, ...]

    temperature: float | None = None

    max_tokens: int | None = None

    stream: bool = False


@dataclass(slots=True, frozen=True)
class GenerateResponse:
    """
    Language model generation response.
    """

    content: str

    finish_reason: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class GenerateStreamChunk:
    """
    Streamed generation chunk.
    """

    content: str = ""

    is_final: bool = False

    finish_reason: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
