"""
Web research tool.

Orchestrates the full pipeline: SearXNG search (google/bing/yahoo) ->
normalize + dedupe URLs -> fetch + extract top N pages concurrently ->
format as context for the agent's LLM prompt.

Fix from the previous version: the SearxngClient import was missing
its `` prefix (`from clients.search_engine.searxng import ...`),
which would raise ImportError at startup.
"""

from __future__ import annotations

from pydantic import Field

from adapters.clients.search_engine.searxng import DEFAULT_ENGINES, SearxngClient
from adapters.observability.logger import get_logger
from agentic.tools.base import Tool, ToolParams
from agentic.tools.search_engine.content_fetch import ContentFetcher
from agentic.tools.search_engine.url_normalizer import normalize_and_dedupe
from core.dto.clients.search_engine import WebPageContent
from core.exceptions.client import ClientConnectionError
from rag.ingestion.sanitizer import SecuritySanitizer, ThreatLevel

log = get_logger(__name__)

WITHHELD_TITLE_MESSAGE = "[title withheld: prompt-injection pattern detected]"


class WebResearchParams(ToolParams):
    # `engines` is deliberately not exposed: which search engines receive
    # a query is not the model's choice.
    query: str = Field(min_length=1, description="What to search the web for.")
    limit: int = Field(default=5, ge=1, le=5, description="How many pages to fetch.")


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

    params_model = WebResearchParams

    def __init__(
        self,
        *,
        searxng_client: SearxngClient,
        content_fetcher: ContentFetcher,
    ) -> None:
        self._searxng = searxng_client
        self._fetcher = content_fetcher
        # ContentFetcher already scans page BODY text (page.text) before
        # it reaches us. Titles are a separate injection vector -- they
        # come from the search engine's/page's own <title>, are just as
        # attacker-controlled, and are interpolated directly into the
        # prompt block below, so they need their own scan.
        self._sanitizer = SecuritySanitizer()

    async def execute(
        self,
        *,
        query: str,
        limit: int = 5,
        engines: tuple[str, ...] = DEFAULT_ENGINES,
    ) -> str:
        log.debug("WebResearchTool.execute(limit=%d, query_length=%d).", limit, len(query))

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
            log.exception("SearXNG search failed.")
            return "Web search failed — please try again."

        deduped = normalize_and_dedupe(raw_results, limit=limit)

        if not deduped:
            return "No search results found."

        pages = await self._fetcher.fetch_many(results=deduped)

        return self._format_for_llm(pages=pages)

    def _format_for_llm(self, *, pages: list[WebPageContent]) -> str:
        blocks = [
            f"Source: {self._safe_title(page.title)}\nURL: {page.url}\n\n{page.text}"
            for page in pages
            if page.fetch_succeeded
        ]

        if not blocks:
            return "Search results found, but no page content could be fetched."

        return "\n\n---\n\n".join(blocks)

    def _safe_title(self, title: str) -> str:
        scan = self._sanitizer.sanitize_and_scan(
            title,
            fail_on=(ThreatLevel.CRITICAL,),
        )

        if not scan.is_safe:
            log.warning(
                "Prompt-injection pattern detected in page title; "
                "title withheld: threat_count=%d.",
                len(scan.threats),
            )
            return WITHHELD_TITLE_MESSAGE

        return scan.clean_text
