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
from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.enums import LLMProviderEnum, MessageRoleEnum
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


async def test_the_local_client_warms_its_model_up_and_keeps_it_loaded() -> None:
    client = LocalLLMClient(base_url="http://localhost:11434", model="m", keep_alive="30m")
    client._client.generate = AsyncMock()

    await client.warm_up()

    # An empty prompt only loads the model (Ollama's documented preload).
    client._client.generate.assert_awaited_once_with(model="m", prompt="", keep_alive="30m")


async def test_the_local_client_asks_every_call_to_keep_the_model_loaded() -> None:
    client = LocalLLMClient(base_url="http://localhost:11434", model="m", keep_alive="30m")
    client._client.chat = AsyncMock(
        return_value=MagicMock(
            message=MagicMock(content="ok"),
            prompt_eval_count=1,
            eval_count=1,
            done_reason="stop",
        )
    )

    await client.generate(
        request=LLMRequestDTO(
            messages=(LLMMessageDTO(role=MessageRoleEnum.USER, content="hi"),),
        )
    )

    assert client._client.chat.await_args.kwargs["keep_alive"] == "30m"


async def test_warm_up_is_a_no_op_for_other_clients() -> None:
    client = GroqClient(api_key="test-key", model="m")

    await client.warm_up()
