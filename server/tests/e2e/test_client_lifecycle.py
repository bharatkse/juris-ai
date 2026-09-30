"""
E2E: the application's LLM clients are closed when it shuts down (review
R17). Runs main.py's real lifespan (as the e2e client fixture does) and
checks the shared resolver closed its Groq and Ollama clients on exit. The
judges use that same resolver, so they hold no clients of their own.

Requires the real Postgres/Redis services with migrations applied. Run via
`make test-e2e`.
"""

from __future__ import annotations

from unittest.mock import patch

from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from adapters.persistence.sqlalchemy.session import dispose_engine
from main import app as fastapi_app


async def test_the_llm_clients_are_closed_on_shutdown() -> None:
    closed: list[str] = []

    async def record_groq(self) -> None:
        closed.append("groq")

    async def record_local(self) -> None:
        closed.append("local")

    await dispose_engine()

    with (
        patch.object(GroqClient, "aclose", record_groq),
        patch.object(LocalLLMClient, "aclose", record_local),
    ):
        async with fastapi_app.router.lifespan_context(fastapi_app):
            assert closed == []

    await dispose_engine()

    assert sorted(closed) == ["groq", "local"]
