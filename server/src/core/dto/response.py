"""
Provider-independent response models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CitationDTO:
    """
    Citation supporting an agent response.
    """

    title: str

    source: str

    reference: str | None = None

    page: int | None = None

    snippet: str | None = None


@dataclass(slots=True, frozen=True)
class SourceDTO:
    """
    Source used to produce an agent response.
    """

    title: str

    uri: str | None = None

    type: str | None = None


@dataclass(slots=True, frozen=True)
class UsageDTO:
    """
    LLM usage associated with an agent response.
    """

    provider: str | None = None

    model: str | None = None

    prompt_tokens: int = 0

    completion_tokens: int = 0

    total_tokens: int = 0

    latency_ms: float | None = None
