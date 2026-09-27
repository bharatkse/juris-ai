"""
LLM resolver composition.

Builds the LLMResolver with all configured providers (Groq, local).
Split out from factories/clients.py so provider wiring can grow
(new providers, retries, health checks) without bloating the client
composition entrypoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from adapters.clients.resolver import LLMResolver
from core.enums import LLMProviderEnum
from core.exceptions.client import ClientProviderError

if TYPE_CHECKING:
    from adapters.clients.llm.base import LLMClient
    from config.settings import Settings


def build_llm_resolver(*, settings: Settings) -> LLMResolver:
    clients: dict[LLMProviderEnum, LLMClient] = {
        LLMProviderEnum.GROQ: GroqClient(
            api_key=settings.llm.groq_api_key or "",
            model=settings.llm.GROQ_MODEL,
        ),
    }

    local_base_url = settings.llm.LLM_LOCAL_BASE_URL
    if local_base_url:
        try:
            clients[LLMProviderEnum.LOCAL] = LocalLLMClient(
                base_url=local_base_url,
                model=settings.llm.LLM_LOCAL_MODEL,
                num_ctx=settings.llm.LLM_LOCAL_NUM_CTX,
            )
        except ClientProviderError:
            pass

    default_provider = LLMProviderEnum.GROQ
    if not settings.llm.groq_api_key and LLMProviderEnum.LOCAL in clients:
        default_provider = LLMProviderEnum.LOCAL

    return LLMResolver(
        clients=clients,
        default_provider=default_provider,
    )
