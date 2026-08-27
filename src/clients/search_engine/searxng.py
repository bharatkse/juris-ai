"""
SearXNG client.

Plain httpx client against the self-hosted SearXNG instance's JSON
API. Not MCP: SearXNG is deployed and owned by Juris-AI itself, and
only Juris-AI code calls it — the same reasoning that moved
rag-server, documents-server, and legal-search-server off MCP. MCP
stays reserved for servers Juris-AI doesn't own the other side of
(clients/mcp/, used for DuckDuckGo, CourtListener, Gmail, Slack).
"""

from __future__ import annotations

import httpx

from src.core.dto.clients.search_engine import SearchEngineResultDTO
from src.core.exceptions.client import ClientConnectionError
from src.core.logger import get_logger

log = get_logger(__name__)

DEFAULT_ENGINES = ("google", "bing", "yahoo")


class SearxngClient:
    """
    Client for a self-hosted SearXNG instance.
    """

    def __init__(self, *, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def search(
        self,
        *,
        query: str,
        engines: tuple[str, ...] = DEFAULT_ENGINES,
        limit: int = 5,
    ) -> list[SearchEngineResultDTO]:
        log.debug(
            "SearXNG search query=%r engines=%s limit=%d.",
            query,
            engines,
            limit,
        )

        try:
            response = await self._client.get(
                f"{self._base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "engines": ",".join(engines),
                },
            )
            response.raise_for_status()

        except httpx.HTTPError as exc:
            log.exception("SearXNG search failed for query=%r.", query)
            raise ClientConnectionError(
                message=f"SearXNG search failed for query '{query}'."
            ) from exc

        payload = response.json()
        raw_results = payload.get("results", [])[:limit]

        return [
            SearchEngineResultDTO(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                engine=r.get("engine", "unknown"),
            )
            for r in raw_results
            if r.get("url")
        ]

    async def close(self) -> None:
        await self._client.aclose()
