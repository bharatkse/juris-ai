"""
Web content fetcher.

Fetches each result URL concurrently and extracts the main readable
text via trafilatura. Failures are isolated per-URL — one bad page
doesn't sink the batch. Content is truncated to keep the eventual LLM
prompt bounded.

Fix from the previous version: a new httpx.AsyncClient was opened and
closed per URL inside fetch_one — no connection reuse even within a
single batch, and no way to reuse the client across calls to
fetch_many. Now a single client is created in __init__ and reused;
call aclose() when the fetcher itself is torn down (e.g. from an
application shutdown hook), not per fetch.

Also fixed: trafilatura.extract is CPU-bound (HTML parsing over a
potentially large page) and was previously called directly inside the
coroutine — offloaded to asyncio.to_thread now, same reasoning as
ParserTool's PDF/DOCX parsing blocking the event loop.

Note on asyncio.Semaphore and event loops: on Python 3.10+,
asyncio.Semaphore no longer binds to a specific event loop at
construction — it resolves the running loop lazily on first
await/acquire. Constructing ContentFetcher before the app's event
loop starts (e.g. at import time) is safe on this project's pinned
Python version. This was a real footgun on Python <3.10, where
Semaphore.__init__ called get_event_loop() eagerly — worth
re-checking only if this project's minimum supported Python version
ever drops below 3.10.
"""

from __future__ import annotations

import asyncio

import httpx
import trafilatura

from adapters.observability.logger import get_logger
from core.dto.clients.search_engine import SearchEngineResultDTO, WebPageContent

log = get_logger(__name__)

DEFAULT_MAX_CONCURRENCY = 5
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_CHARS = 4000  # per-page cap fed to the LLM


class ContentFetcher:
    """
    Fetches and extracts readable text from a batch of URLs.
    """

    def __init__(
        self,
        *,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_chars = max_chars
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "juris-ai-research-bot/1.0"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_one(self, *, result: SearchEngineResultDTO) -> WebPageContent:
        async with self._semaphore:
            try:
                response = await self._client.get(result.url)
                response.raise_for_status()

            except httpx.HTTPError as exc:
                log.warning("Fetch failed for %s: %s.", result.url, exc)
                return WebPageContent(
                    url=result.url,
                    title=result.title,
                    text="",
                    fetch_succeeded=False,
                    error=str(exc),
                )

            try:
                extracted = await asyncio.to_thread(
                    trafilatura.extract,
                    response.text,
                    include_comments=False,
                    include_tables=False,
                    favor_precision=True,
                )

            except Exception as exc:
                # trafilatura is a third-party parser over arbitrary
                # HTML — isolate any parsing failure per-URL rather
                # than letting it escape and take down fetch_many's
                # gather.
                log.warning("Content extraction failed for %s: %s.", result.url, exc)
                return WebPageContent(
                    url=result.url,
                    title=result.title,
                    text="",
                    fetch_succeeded=False,
                    error=f"Extraction failed: {exc}",
                )

            if not extracted:
                log.warning("No extractable content for %s.", result.url)
                return WebPageContent(
                    url=result.url,
                    title=result.title,
                    text="",
                    fetch_succeeded=False,
                    error="No extractable content.",
                )

            return WebPageContent(
                url=result.url,
                title=result.title,
                text=extracted[: self._max_chars],
                fetch_succeeded=True,
            )

    async def fetch_many(
        self,
        *,
        results: list[SearchEngineResultDTO],
    ) -> list[WebPageContent]:
        if not results:
            return []

        raw = await asyncio.gather(
            *(self.fetch_one(result=r) for r in results),
            return_exceptions=True,
        )

        pages: list[WebPageContent] = []

        for result, outcome in zip(results, raw, strict=True):
            if isinstance(outcome, BaseException):
                # Defense in depth — fetch_one already catches the
                # exceptions we expect; this only fires for something
                # genuinely unanticipated.
                log.exception("Unexpected error fetching %s.", result.url, exc_info=outcome)
                pages.append(
                    WebPageContent(
                        url=result.url,
                        title=result.title,
                        text="",
                        fetch_succeeded=False,
                        error=str(outcome),
                    )
                )
            else:
                pages.append(outcome)

        succeeded = sum(1 for p in pages if p.fetch_succeeded)
        log.info("Fetched %d/%d page(s) successfully.", succeeded, len(pages))

        return pages
