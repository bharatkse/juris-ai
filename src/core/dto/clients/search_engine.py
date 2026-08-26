"""
Provider-independent web search models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class SearchEngineRequestDTO:
    """
    Request sent to a web search provider.
    """

    query: str

    max_results: int = 5

    metadata: Mapping[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class SearchEngineResultDTO:
    """
    A single search result.
    """

    title: str

    url: str

    snippet: str

    metadata: Mapping[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class SearchEngineResponseDTO:
    """
    Response returned by a web search provider.
    """

    results: tuple[SearchEngineResultDTO, ...]

    metadata: Mapping[str, Any] = field(
        default_factory=dict,
    )


class WebPageContent:
    pass
