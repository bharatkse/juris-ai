"""
Provider-independent web search models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class WebSearchRequest:
    """
    Request sent to a web search provider.
    """

    query: str

    max_results: int = 5

    metadata: Mapping[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class WebSearchResult:
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
class WebSearchResponse:
    """
    Response returned by a web search provider.
    """

    results: tuple[WebSearchResult, ...]

    metadata: Mapping[str, Any] = field(
        default_factory=dict,
    )
