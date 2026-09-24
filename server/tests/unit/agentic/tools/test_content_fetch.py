"""
Unit tests for ContentFetcher's outbound-request safety (SSRF).

Search results are third-party URLs: a page must not be able to point or
redirect the server at internal addresses (cloud metadata, loopback,
private networks). httpx is driven through a MockTransport that records
every request, so each test can assert an internal address was never
contacted, not just that the fetch failed.
"""

from __future__ import annotations

import httpx
import pytest

from agentic.tools.search_engine import content_fetch
from agentic.tools.search_engine.content_fetch import ContentFetcher
from core.dto.clients.search_engine import SearchEngineResultDTO

PAGE = (
    "<html><head><title>Act</title></head><body><article>"
    + "".join(
        f"<p>Section {i} of the Information Technology Act describes the obligations "
        f"of intermediaries and the penalties that apply when those obligations are "
        f"not met, with worked examples for paragraph {i}.</p>"
        for i in range(8)
    )
    + "</article></body></html>"
)

DNS = {
    "public.example": ["93.184.216.34"],
    "other-public.example": ["93.184.216.35"],
    "internal.example": ["10.0.0.5"],
    "loopback.example": ["127.0.0.1"],
    "mixed.example": ["93.184.216.34", "192.168.1.10"],
}


@pytest.fixture
def requested(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    Route ContentFetcher's httpx client through a recording MockTransport
    and a fake resolver; return the list of URLs actually requested.
    """

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        seen.append(url)
        host = request.url.host
        path = request.url.path
        if host == "169.254.169.254" or host in {"10.0.0.5", "127.0.0.1"}:
            return httpx.Response(200, text="SECRET-INTERNAL-DATA")
        if path == "/redirect-to-metadata":
            return httpx.Response(
                302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
            )
        if path == "/redirect-to-internal-name":
            return httpx.Response(301, headers={"location": "http://internal.example/admin"})
        if path == "/redirect-to-public":
            return httpx.Response(302, headers={"location": "https://other-public.example/page"})
        if path.startswith("/loop"):
            n = int(path.removeprefix("/loop") or 0)
            return httpx.Response(302, headers={"location": f"/loop{n + 1}"})
        return httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})

    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    async def fake_resolve(host: str, port: int) -> list[str]:
        if host not in DNS:
            raise OSError("NXDOMAIN")
        return DNS[host]

    monkeypatch.setattr(content_fetch.httpx, "AsyncClient", client_factory)
    # raising=False: lets the same test run against code without the resolver.
    monkeypatch.setattr(content_fetch, "_resolve_host", fake_resolve, raising=False)
    return seen


async def _fetch(url: str):
    fetcher = ContentFetcher()
    try:
        return await fetcher.fetch_one(
            result=SearchEngineResultDTO(title="t", url=url, snippet="s")
        )
    finally:
        await fetcher.close()


def _internal_contacted(seen: list[str]) -> bool:
    return any(
        h in u
        for u in seen
        for h in ("169.254.169.254", "10.0.0.5", "127.0.0.1", "internal.example")
    )


@pytest.mark.asyncio
async def test_public_page_is_fetched(requested: list[str]) -> None:
    page = await _fetch("https://public.example/act")

    assert page.fetch_succeeded is True
    assert "Information Technology Act" in page.text


@pytest.mark.asyncio
async def test_redirect_to_cloud_metadata_is_blocked_before_request(requested: list[str]) -> None:
    page = await _fetch("https://public.example/redirect-to-metadata")

    assert page.fetch_succeeded is False
    assert "SECRET-INTERNAL-DATA" not in page.text
    assert not _internal_contacted(requested)
    assert page.error == content_fetch.BLOCKED_DESTINATION_MESSAGE


@pytest.mark.asyncio
async def test_redirect_to_name_resolving_privately_is_blocked(requested: list[str]) -> None:
    page = await _fetch("https://public.example/redirect-to-internal-name")

    assert page.fetch_succeeded is False
    assert not _internal_contacted(requested)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/api/v1/health",
        "http://loopback.example/",
        "http://internal.example/",
        "http://mixed.example/",
        "http://[::ffff:127.0.0.1]/",
        "http://[::1]/",
        "http://0.0.0.0/",
    ],
)
async def test_direct_internal_destinations_are_blocked(requested: list[str], url: str) -> None:
    page = await _fetch(url)

    assert page.fetch_succeeded is False
    assert requested == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://public.example/x", "gopher://public.example/"]
)
async def test_non_http_schemes_are_blocked(requested: list[str], url: str) -> None:
    page = await _fetch(url)

    assert page.fetch_succeeded is False
    assert requested == []


@pytest.mark.asyncio
async def test_redirect_to_another_public_host_is_followed(requested: list[str]) -> None:
    page = await _fetch("https://public.example/redirect-to-public")

    assert page.fetch_succeeded is True
    assert requested[-1] == "https://other-public.example/page"


@pytest.mark.asyncio
async def test_redirect_chain_is_capped(requested: list[str]) -> None:
    page = await _fetch("https://public.example/loop0")

    assert page.fetch_succeeded is False
    assert len(requested) == content_fetch.MAX_REDIRECTS + 1


def test_client_does_not_follow_redirects_itself() -> None:
    fetcher = ContentFetcher()

    assert fetcher._client.follow_redirects is False
