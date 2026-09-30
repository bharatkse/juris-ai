"""
LLM clients are closed on shutdown (review R17): each client closes its
provider SDK's HTTP client, the resolver closes every client it holds, and
the app's lifespan closes the shared resolver (close_clients()).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from adapters.clients.resolver import LLMResolver
from core.enums import LLMProviderEnum
from wiring.factories.clients import close_clients


async def test_the_groq_client_closes_its_http_client() -> None:
    client = GroqClient(api_key="test-key", model="m")

    await client.aclose()

    assert client._client.is_closed()


async def test_the_local_client_closes_its_http_client() -> None:
    client = LocalLLMClient(base_url="http://localhost:11434", model="m")

    await client.aclose()

    assert client._client._client.is_closed


async def test_the_resolver_closes_every_client_it_holds() -> None:
    groq, local = MagicMock(), MagicMock()
    groq.aclose, local.aclose = AsyncMock(), AsyncMock()
    resolver = LLMResolver(
        clients={LLMProviderEnum.GROQ: groq, LLMProviderEnum.LOCAL: local},
        default_provider=LLMProviderEnum.GROQ,
    )

    await resolver.aclose()

    groq.aclose.assert_awaited_once()
    local.aclose.assert_awaited_once()


async def test_close_clients_closes_the_shared_resolver() -> None:
    clients = MagicMock()
    clients.llm_resolver.aclose = AsyncMock()

    await close_clients(clients)

    clients.llm_resolver.aclose.assert_awaited_once()
