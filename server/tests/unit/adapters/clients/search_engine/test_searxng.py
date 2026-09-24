"""
Unit tests for SearxngClient, against a mocked SearXNG HTTP endpoint.
"""

from __future__ import annotations

import httpx
import pytest

from adapters.clients.search_engine.searxng import SearxngClient
from agentic.tools.search_engine.url_normalizer import normalize_and_dedupe
from core.exceptions.client import ClientConnectionError


def _client(handler: httpx.MockTransport) -> SearxngClient:
    client = SearxngClient(base_url="http://searxng.test")
    client._client = httpx.AsyncClient(transport=handler)
    return client


def _json_transport(payload: dict) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(200, json=payload))


async def test_search_maps_results_and_keeps_engine_in_metadata() -> None:
    client = _client(
        _json_transport(
            {
                "results": [
                    {
                        "title": "IT Act",
                        "url": "https://example.org/a",
                        "content": "s66",
                        "engine": "google",
                    },
                    {"title": "No engine", "url": "https://example.org/b", "content": ""},
                ]
            }
        )
    )

    results = await client.search(query="section 66", limit=5)

    assert [(r.title, r.url, r.snippet) for r in results] == [
        ("IT Act", "https://example.org/a", "s66"),
        ("No engine", "https://example.org/b", ""),
    ]
    assert [r.metadata["engine"] for r in results] == ["google", "unknown"]


async def test_search_drops_results_without_url_and_applies_limit() -> None:
    client = _client(
        _json_transport(
            {"results": [{"title": "x"}, *({"url": f"https://e.org/{i}"} for i in range(5))]}
        )
    )

    results = await client.search(query="q", limit=3)

    # limit is applied to the raw list first, then URL-less entries dropped
    assert [r.url for r in results] == ["https://e.org/0", "https://e.org/1"]


async def test_search_wraps_http_errors() -> None:
    client = _client(httpx.MockTransport(lambda request: httpx.Response(502)))

    with pytest.raises(ClientConnectionError):
        await client.search(query="q")


async def test_dedupe_preserves_metadata() -> None:
    client = _client(
        _json_transport(
            {
                "results": [
                    {"url": "https://Example.org/a/", "engine": "google"},
                    {"url": "https://example.org/a", "engine": "bing"},
                ]
            }
        )
    )

    deduped = normalize_and_dedupe(await client.search(query="q"), limit=5)

    assert len(deduped) == 1
    assert deduped[0].metadata == {"engine": "google"}
