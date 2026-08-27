"""
URL normalization.

Same article often appears from multiple engines (Google, Bing,
Yahoo) with different tracking params or redirect wrappers. Normalize
before dedup so "top N" means N distinct pages, not N URL variants of
fewer pages.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from adapters.observability.logger import get_logger
from core.dto.clients.search_engine import SearchEngineResultDTO

log = get_logger(__name__)

# Query params to strip — tracking/analytics noise that doesn't
# change the underlying resource.
_TRACKING_PARAM_PREFIXES = ("utm_", "ref", "fbclid", "gclid", "mc_cid", "mc_eid")


def normalize_url(url: str) -> str:
    """
    Canonicalize a URL: force https scheme, lowercase host, strip
    fragment, drop tracking query params, drop trailing slash.
    """

    parsed = urlparse(url)

    scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
    netloc = parsed.netloc.lower()

    kept_params = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not any(k.lower().startswith(p) for p in _TRACKING_PARAM_PREFIXES)
    ]
    query = urlencode(kept_params)

    path = parsed.path.rstrip("/") or "/"

    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_and_dedupe(
    results: list[SearchEngineResultDTO],
    *,
    limit: int,
) -> list[SearchEngineResultDTO]:
    """
    Normalize URLs and drop duplicates, keeping the first (highest-
    ranked) occurrence of each canonical URL. Returns at most `limit`
    results.
    """

    seen: set[str] = set()
    deduped: list[SearchEngineResultDTO] = []

    for result in results:
        canonical = normalize_url(result.url)

        if canonical in seen:
            continue

        seen.add(canonical)
        deduped.append(
            SearchEngineResultDTO(
                title=result.title,
                url=canonical,
                snippet=result.snippet,
                engine=result.engine,
            )
        )

        if len(deduped) >= limit:
            break

    log.debug(
        "Deduped %d raw result(s) to %d unique URL(s) (limit=%d).",
        len(results),
        len(deduped),
        limit,
    )

    return deduped
