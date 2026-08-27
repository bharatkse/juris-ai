"""
Web research tool.

Orchestrates the full pipeline: SearXNG search (google/bing/yahoo) ->
normalize + dedupe URLs -> fetch + extract top N pages concurrently ->
format as context for the agent's LLM prompt.

Fix from the previous version: the SearxngClient import was missing
its `src.` prefix (`from clients.search_engine.searxng import ...`),
which would raise ImportError at startup.
"""

from __future__ import annotations

from src.clients.search_engine.searxng import DEFAULT_ENGINES, SearxngClient
from src.core.dto.clients.search_engine import WebPageContent
from src.core.exceptions.client import ClientConnectionError
from src.core.logger import get_logger
from src.tools.base import Tool
from src.tools.search_engine.content_fetch import ContentFetcher
from src.tools.search_engine.url_normalizer import normalize_and_dedupe

log = get_logger(__name__)


class WebResearchTool(Tool):
    """
    Search + fetch + extract, in one call. Returns formatted context
    ready to drop into an LLM prompt.
    """

    name = "web_research"
    description = (
        "Search the web (Google, Bing, Yahoo via SearXNG), fetch the "
        "top results, and return their extracted page content — use "
        "when full article/page content is needed, not just a "
        "search snippet."
    )

    def __init__(
        self,
        *,
        searxng_client: SearxngClient,
        content_fetcher: ContentFetcher,
    ) -> None:
        self._searxng = searxng_client
        self._fetcher = content_fetcher

    async def execute(
        self,
        *,
        query: str,
        limit: int = 5,
        engines: tuple[str, ...] = DEFAULT_ENGINES,
    ) -> str:
        log.debug("WebResearchTool.execute(query=%r, limit=%d).", query, limit)

        try:
            # Fetch more than `limit` from search since dedup may
            # collapse some — 3x is a reasonable safety margin
            # without over-fetching.
            raw_results = await self._searxng.search(
                query=query,
                engines=engines,
                limit=limit * 3,
            )

        except ClientConnectionError:
            log.exception("SearXNG search failed for query=%r.", query)
            return "Web search failed — please try again."

        deduped = normalize_and_dedupe(raw_results, limit=limit)

        if not deduped:
            return "No search results found."

        pages = await self._fetcher.fetch_many(results=deduped)

        return self._format_for_llm(pages=pages)

    @staticmethod
    def _format_for_llm(*, pages: list[WebPageContent]) -> str:
        blocks = [
            f"Source: {page.title}\nURL: {page.url}\n\n{page.text}"
            for page in pages
            if page.fetch_succeeded
        ]

        if not blocks:
            return "Search results found, but no page content could be fetched."

        return "\n\n---\n\n".join(blocks)
