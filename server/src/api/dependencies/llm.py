"""
Ad-hoc (non-agent) LLM client dependency.

For request-scoped, one-off LLM calls outside the agent execution
graph (e.g. conversation summarization). Builds a fresh LLMResolver
per call rather than sharing the app-wide singleton -- the same
pattern wiring/factories/evaluation.py::build_llm_judge already uses
for the RAG faithfulness judge. This is deliberately not wired through
app.state (unlike AIOrchestrator): build_llm_resolver() only
constructs lightweight client wrapper objects (API key/base URL/model
strings), not anything with real startup cost like the embedding
model, so re-building it per request is cheap and avoids threading a
second shared singleton through app.state for a rarely-hit path.
"""

from __future__ import annotations

from adapters.clients.llm.base import LLMClient
from config.settings import get_settings
from wiring.factories.llm_resolver import build_llm_resolver


def get_llm_client() -> LLMClient:
    """
    Return the default-provider LLM client for one-off, non-agent use.
    """

    settings = get_settings()

    return build_llm_resolver(settings=settings).get()
