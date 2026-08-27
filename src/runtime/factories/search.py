"""
Search client composition.

Builds the self-hosted SearXNG client and the content fetcher used by
WebResearchTool. Separate from factories/clients.py's LLM/MCP wiring
since this is plain HTTP infra, not LLM providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.clients.search_engine.searxng import SearxngClient
from src.tools.search_engine.content_fetch import ContentFetcher

if TYPE_CHECKING:
    from src.core.config import Settings


def build_searxng_client(*, settings: Settings) -> SearxngClient:
    return SearxngClient(base_url=settings.searxng_base_url)


def build_content_fetcher(*, settings: Settings) -> ContentFetcher:
    return ContentFetcher(
        max_concurrency=settings.web_research_max_concurrency,
        timeout_seconds=settings.web_research_fetch_timeout_seconds,
        max_chars=settings.web_research_max_chars_per_page,
    )
