"""
Builders for provider-independent web search models.
"""

from __future__ import annotations

from typing import Any

from src.core.dto.clients.web_search import (
    WebSearchRequestDTO,
    WebSearchResponseDTO,
    WebSearchResultDTO,
)


def build_web_search_request(
    *,
    query: str = "What is contract law?",
    max_results: int = 5,
    metadata: dict[str, Any] | None = None,
) -> WebSearchRequestDTO:
    """
    Build a WebSearchRequest.
    """

    return WebSearchRequestDTO(
        query=query,
        max_results=max_results,
        metadata=metadata or {},
    )


def build_web_search_result(
    *,
    title: str = "Contract Law - Wikipedia",
    url: str = "https://en.wikipedia.org/wiki/Contract",
    snippet: str = "Contract law governs legally enforceable agreements.",
    metadata: dict[str, Any] | None = None,
) -> WebSearchResultDTO:
    """
    Build a WebSearchResult.
    """

    return WebSearchResultDTO(
        title=title,
        url=url,
        snippet=snippet,
        metadata=metadata or {},
    )


def build_web_search_response(
    *,
    results: tuple[WebSearchResultDTO, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> WebSearchResponseDTO:
    """
    Build a WebSearchResponse.
    """

    return WebSearchResponseDTO(
        results=results or (build_web_search_result(),),
        metadata=metadata or {},
    )


def build_web_search_results(
    count: int = 3,
) -> tuple[WebSearchResultDTO, ...]:
    """
    Build multiple search results.
    """

    return tuple(
        build_web_search_result(
            title=f"Result {index}",
            url=f"https://example.com/{index}",
            snippet=f"Snippet {index}",
        )
        for index in range(1, count + 1)
    )
