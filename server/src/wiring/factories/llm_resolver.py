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

if TYPE_CHECKING:
    from config.settings import Settings


def build_llm_resolver(*, settings: Settings) -> LLMResolver:
    return LLMResolver(
        clients={
            LLMProviderEnum.GROQ: GroqClient(
                api_key=settings.llm.groq_api_key,
                model=settings.llm.GROQ_MODEL,
            ),
            LLMProviderEnum.LOCAL: LocalLLMClient(
                base_url=settings.llm.LLM_LOCAL_BASE_URL,
                model=settings.llm.LLM_LOCAL_MODEL,
            ),
        },
        default_provider=LLMProviderEnum.GROQ,
    )
