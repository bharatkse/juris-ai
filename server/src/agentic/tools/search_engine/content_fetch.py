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
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura

from adapters.observability.logger import get_logger
from core.dto.clients.search_engine import SearchEngineResultDTO, WebPageContent
from rag.ingestion.sanitizer import SecuritySanitizer, ThreatLevel

log = get_logger(__name__)

DEFAULT_MAX_CONCURRENCY = 5
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_CHARS = 4000  # per-page cap fed to the LLM

WITHHELD_CONTENT_MESSAGE = "[content withheld: prompt-injection pattern detected in fetched page]"

MAX_REDIRECTS = 3
ALLOWED_SCHEMES = frozenset({"http", "https"})
BLOCKED_DESTINATION_MESSAGE = "Blocked: destination is not allowed."


class UnsafeURLError(ValueError):
    """A URL whose scheme or resolved address must not be fetched."""


async def _resolve_host(host: str, port: int) -> list[str]:
    """Resolve ``host`` to every IP address it maps to."""

    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # is_global excludes private, loopback, link-local (incl. cloud
    # metadata 169.254.169.254), reserved, unspecified and shared
    # (100.64/10) ranges; multicast is rejected separately.
    return ip.is_global and not ip.is_multicast


async def _ensure_fetchable(url: str) -> None:
    """
    Reject non-http(s) URLs and any host that resolves to a non-public
    address. Every resolved address must be public, so a name with one
    public and one internal record is still refused.
    """

    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme not allowed: {parts.scheme!r}")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("URL has no host")
    port = parts.port or (443 if parts.scheme.lower() == "https" else 80)

    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            addresses = await _resolve_host(host, port)
        except OSError as exc:
            raise UnsafeURLError(f"cannot resolve host {host!r}") from exc

    if not addresses or not all(_is_public_address(a) for a in addresses):
        raise UnsafeURLError(f"host {host!r} resolves to a non-public address")


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
        # Redirects are followed manually in _get() so every hop's
        # destination is validated before it is requested.
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "juris-ai-research-bot/1.0"},
        )
        # Fetched pages are arbitrary, untrusted third-party content --
        # the same threat model the RAG ingestion sanitizer already
        # covers for uploaded documents. Stateless, safe to share.
        self._sanitizer = SecuritySanitizer()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str) -> httpx.Response:
        """
        GET ``url``, following at most MAX_REDIRECTS redirects and
        validating the destination of every hop before requesting it.
        Search results are third-party URLs, so a public page could
        otherwise redirect the server into internal addresses.
        """

        for _ in range(MAX_REDIRECTS + 1):
            await _ensure_fetchable(url)
            response = await self._client.get(url)
            if not response.is_redirect:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            url = urljoin(str(response.url), location)

        raise httpx.TooManyRedirects(
            f"Exceeded {MAX_REDIRECTS} redirects.",
            request=response.request,
        )

    async def fetch_one(self, *, result: SearchEngineResultDTO) -> WebPageContent:
        async with self._semaphore:
            try:
                response = await self._get(result.url)
                response.raise_for_status()

            except UnsafeURLError as exc:
                log.warning("Fetch blocked for %s: %s.", result.url, exc)
                return WebPageContent(
                    url=result.url,
                    title=result.title,
                    text="",
                    fetch_succeeded=False,
                    error=BLOCKED_DESTINATION_MESSAGE,
                )

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

            # Fetched page text is untrusted and will be dropped directly
            # into the agent's LLM prompt (WebResearchTool._format_for_llm).
            # Scan the full extracted text (before truncation, so a
            # pattern positioned after max_chars is not missed) and
            # withhold the page entirely on a CRITICAL finding rather
            # than forwarding it -- do not silently pass it through.
            scan = self._sanitizer.sanitize_and_scan(
                extracted,
                fail_on=(ThreatLevel.CRITICAL,),
            )

            if not scan.is_safe:
                log.warning(
                    "Prompt-injection pattern detected in fetched page; "
                    "content withheld: url=%s threat_count=%d.",
                    result.url,
                    len(scan.threats),
                )
                return WebPageContent(
                    url=result.url,
                    title=result.title,
                    text=WITHHELD_CONTENT_MESSAGE,
                    fetch_succeeded=True,
                )

            return WebPageContent(
                url=result.url,
                title=result.title,
                text=scan.clean_text[: self._max_chars],
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
