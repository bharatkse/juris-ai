"""
Search client composition.

Builds the self-hosted SearXNG client and the content fetcher used by
WebResearchTool. Separate from factories/clients.py's LLM/MCP wiring
since this is plain HTTP infra, not LLM providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.clients.search_engine.searxng import SearxngClient
from agentic.tools.search_engine.content_fetch import ContentFetcher

if TYPE_CHECKING:
    from config.settings import Settings


def build_searxng_client(*, settings: Settings) -> SearxngClient:
    return SearxngClient(base_url=settings.llm.SEARXNG_BASE_URL)


def build_content_fetcher(*, settings: Settings) -> ContentFetcher:
    return ContentFetcher(
        max_concurrency=settings.llm.web_research_max_concurrency,
        timeout_seconds=settings.llm.web_research_fetch_timeout_seconds,
        max_chars=settings.llm.web_research_max_chars_per_page,
    )
