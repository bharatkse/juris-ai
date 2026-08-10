"""
Runtime client composition.

Creates all shared external service clients used by the AI runtime.

Responsibilities:

- Create LLM clients
- Create web search clients
- Assemble the client container

No business logic belongs in this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.clients.llm.groq import GroqClient
from src.clients.web_search.brave import BraveClient
from src.runtime.containers import ClientContainer

if TYPE_CHECKING:
    from src.core.config import Settings


def create_clients(
    *,
    settings: Settings,
) -> ClientContainer:
    """
    Create shared external service clients.

    All clients are created once during application startup
    and reused for the lifetime of the application.
    """

    llm_client = GroqClient(
        api_key=settings.GROQ_API_KEY.get_secret_value(),
        model=settings.GROQ_MODEL,
    )

    web_search_client = BraveClient(
        api_key=settings.BRAVE_API_KEY.get_secret_value(),
    )

    return ClientContainer(
        llm_client=llm_client,
        web_search_client=web_search_client,
    )
