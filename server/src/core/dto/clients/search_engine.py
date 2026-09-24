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


@dataclass(slots=True, frozen=True)
class WebPageContent:
    """
    Extracted content from one fetched web page.

    Previously this was an empty stub (`class WebPageContent: pass`),
    while every caller (content_fetch.py, web_research.py) constructed
    it with url/title/text/fetch_succeeded/error keyword arguments --
    a TypeError on every call, so WebResearchTool crashed on any real
    fetch. Fields below match that pre-existing call-site contract.
    """

    url: str

    title: str

    text: str

    fetch_succeeded: bool

    error: str | None = None
