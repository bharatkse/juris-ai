"""
Brave Search client.
"""

from __future__ import annotations

from typing import Final

from httpx import ConnectError, HTTPStatusError, TimeoutException

from core.exceptions.client import (
    ClientConnectionError,
    ClientProviderError,
    ClientRateLimitError,
    ClientTimeoutError,
)
from src.clients.helper import map_exception
from src.clients.http import AsyncHTTPClient
from src.clients.web_search.base import WebSearchClient
from src.clients.web_search.models import (
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResult,
)
from src.core.logger import get_logger

log = get_logger(__name__)


class BraveClient(
    AsyncHTTPClient,
    WebSearchClient,
):
    """
    Brave Search API client.
    """

    _BASE_URL: Final = "https://api.search.brave.com/res/v1"

    def __init__(
        self,
        *,
        api_key: str,
    ) -> None:
        super().__init__(
            base_url=self._BASE_URL,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
        )

    async def search(
        self,
        *,
        request: WebSearchRequest,
    ) -> WebSearchResponse:
        """
        Search the web using Brave Search.
        """

        log.info(
            "Searching Brave for query '%s'.",
            request.query,
        )

        try:
            payload = await self.get_json(
                "/web/search",
                params={
                    "q": request.query,
                    "count": request.max_results,
                },
            )

        except Exception as exc:
            log.exception(
                "Brave search failed for query '%s'.",
                request.query,
            )

            raise map_exception(
                exc=exc,
                mappings={
                    TimeoutException: lambda _: ClientTimeoutError(),
                    ConnectError: lambda _: ClientConnectionError(),
                    HTTPStatusError: lambda _: ClientRateLimitError(),
                },
                default=lambda e: ClientProviderError(
                    message=str(e),
                ),
            ) from exc

        search_results = payload.get(
            "web",
            {},
        ).get(
            "results",
            [],
        )

        results = tuple(
            WebSearchResult(
                title=result["title"],
                url=result["url"],
                snippet=result.get(
                    "description",
                    "",
                ),
            )
            for result in search_results
        )

        log.info(
            "Brave search returned %d result(s) for query '%s'.",
            len(results),
            request.query,
        )

        return WebSearchResponse(
            results=results,
            metadata={
                "provider": "brave",
            },
        )
