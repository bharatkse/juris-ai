"""
Runtime client composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.clients.mcp.registry import MCPServerRegistry
from adapters.clients.resolver import LLMResolver
from wiring.containers import ClientContainer
from wiring.factories.cache import build_cache
from wiring.factories.llm_resolver import build_llm_resolver
from wiring.factories.mcp import build_mcp_registry
from wiring.factories.rag import build_rag_pipeline
from wiring.factories.search import build_content_fetcher, build_searxng_client

if TYPE_CHECKING:
    from config.settings import Settings


def create_clients(*, settings: Settings) -> ClientContainer:
    llm_resolver: LLMResolver = build_llm_resolver(settings=settings)
    mcp_registry: MCPServerRegistry = build_mcp_registry(settings=settings)
    # Built once, shared by build_rag_pipeline() (embedding memoization)
    # and build_faithfulness_backend() (judge memoization, wired in
    # factories/executor.py) -- see wiring/factories/cache.py.
    cache = build_cache(settings=settings)
    rag_pipeline = build_rag_pipeline(settings=settings, cache=cache)

    return ClientContainer(
        llm_resolver=llm_resolver,
        mcp_registry=mcp_registry,
        searxng_client=build_searxng_client(settings=settings),
        content_fetcher=build_content_fetcher(settings=settings),
        # Loads the embedding + reranker models exactly once, here,
        # at process startup.
        hybrid_retriever=rag_pipeline.hybrid_retriever,
        embedding_provider=rag_pipeline.embedding_provider,
        cache=cache,
    )
