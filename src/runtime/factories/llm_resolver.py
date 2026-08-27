"""
LLM resolver composition.

Builds the LLMResolver with all configured providers (Groq, local).
Split out from factories/clients.py so provider wiring can grow
(new providers, retries, health checks) without bloating the client
composition entrypoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.clients.llm.groq import GroqClient
from src.clients.llm.local import LocalLLMClient
from src.clients.resolver import LLMResolver
from src.core.enums import LLMProviderEnum

if TYPE_CHECKING:
    from src.core.config import Settings


def build_llm_resolver(*, settings: Settings) -> LLMResolver:
    return LLMResolver(
        clients={
            LLMProviderEnum.GROQ: GroqClient(
                api_key=settings.groq_api_key,
                model=settings.GROQ_MODEL,
            ),
            LLMProviderEnum.LOCAL: LocalLLMClient(
                base_url=settings.LLM_LOCAL_BASE_URL,
                model=settings.LLM_LOCAL_MODEL,
            ),
        },
        default_provider=LLMProviderEnum.GROQ,
    )
