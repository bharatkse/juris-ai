"""
Runtime client composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.clients.mcp.registry import MCPServerRegistry
from src.clients.resolver import LLMResolver
from src.runtime.containers import ClientContainer
from src.runtime.factories.llm_resolver import build_llm_resolver
from src.runtime.factories.mcp import build_mcp_registry
from src.runtime.factories.rag import build_hybrid_retriever
from src.runtime.factories.search import build_content_fetcher, build_searxng_client

if TYPE_CHECKING:
    from src.core.config import Settings


def create_clients(*, settings: Settings) -> ClientContainer:
    llm_resolver: LLMResolver = build_llm_resolver(settings=settings)
    mcp_registry: MCPServerRegistry = build_mcp_registry(settings=settings)

    return ClientContainer(
        llm_resolver=llm_resolver,
        mcp_registry=mcp_registry,
        searxng_client=build_searxng_client(settings=settings),
        content_fetcher=build_content_fetcher(settings=settings),
        # Loads the embedding + reranker models exactly once, here,
        # at process startup.
        hybrid_retriever=build_hybrid_retriever(settings=settings),
    )
