"""
Builders for provider-independent web search models.
"""

from __future__ import annotations

from typing import Any

from src.clients.web_search.models import (
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResult,
)


def build_web_search_request(
    *,
    query: str = "What is contract law?",
    max_results: int = 5,
    metadata: dict[str, Any] | None = None,
) -> WebSearchRequest:
    """
    Build a WebSearchRequest.
    """

    return WebSearchRequest(
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
) -> WebSearchResult:
    """
    Build a WebSearchResult.
    """

    return WebSearchResult(
        title=title,
        url=url,
        snippet=snippet,
        metadata=metadata or {},
    )


def build_web_search_response(
    *,
    results: tuple[WebSearchResult, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> WebSearchResponse:
    """
    Build a WebSearchResponse.
    """

    return WebSearchResponse(
        results=results or (build_web_search_result(),),
        metadata=metadata or {},
    )


def build_web_search_results(
    count: int = 3,
) -> tuple[WebSearchResult, ...]:
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
