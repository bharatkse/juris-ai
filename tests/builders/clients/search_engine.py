"""
Builders for provider-independent web search models.
"""

from __future__ import annotations

from typing import Any

from src.core.dto.clients.search_engine import (
    SearchEngineRequestDTO,
    SearchEngineResponseDTO,
    SearchEngineResultDTO,
)


def build_search_engine_request(
    *,
    query: str = "What is contract law?",
    max_results: int = 5,
    metadata: dict[str, Any] | None = None,
) -> SearchEngineRequestDTO:
    """
    Build a WebSearchRequest.
    """

    return SearchEngineRequestDTO(
        query=query,
        max_results=max_results,
        metadata=metadata or {},
    )


def build_search_engine_result(
    *,
    title: str = "Contract Law - Wikipedia",
    url: str = "https://en.wikipedia.org/wiki/Contract",
    snippet: str = "Contract law governs legally enforceable agreements.",
    metadata: dict[str, Any] | None = None,
) -> SearchEngineResultDTO:
    """
    Build a WebSearchResult.
    """

    return SearchEngineResultDTO(
        title=title,
        url=url,
        snippet=snippet,
        metadata=metadata or {},
    )


def build_search_engine_response(
    *,
    results: tuple[SearchEngineResultDTO, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> SearchEngineResponseDTO:
    """
    Build a WebSearchResponse.
    """

    return SearchEngineResponseDTO(
        results=results or (build_search_engine_result(),),
        metadata=metadata or {},
    )


def build_search_engine_results(
    count: int = 3,
) -> tuple[SearchEngineResultDTO, ...]:
    """
    Build multiple search results.
    """

    return tuple(
        build_search_engine_result(
            title=f"Result {index}",
            url=f"https://example.com/{index}",
            snippet=f"Snippet {index}",
        )
        for index in range(1, count + 1)
    )
