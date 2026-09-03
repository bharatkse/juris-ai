"""
Runtime dependency containers.

Defines immutable containers used by the runtime composition root to
group shared dependencies during application startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.clients.mcp.registry import MCPServerRegistry
    from adapters.clients.resolver import LLMResolver
    from adapters.clients.search_engine.searxng import SearxngClient
    from agentic.execution.executor import Executor
    from agentic.execution.validation.response import ResponseValidator
    from agentic.planning.planner import ExecutionPlanner
    from agentic.registry.protocols import AgentRegistryProtocol, ToolRegistryProtocol
    from agentic.tools.search_engine.content_fetch import ContentFetcher
    from application.authorization.service import AuthorizationService
    from rag.hybrid_retriever import HybridRetriever


@dataclass(frozen=True, slots=True)
class ClientContainer:
    llm_resolver: LLMResolver
    mcp_registry: MCPServerRegistry
    searxng_client: SearxngClient
    content_fetcher: ContentFetcher
    # Built once at startup (factories/rag.py) — holds the loaded
    # embedding + reranker models. Never reconstruct this per-request.
    hybrid_retriever: HybridRetriever


@dataclass(frozen=True, slots=True)
class RegistryContainer:
    agent_registry: AgentRegistryProtocol
    tool_registry: ToolRegistryProtocol


@dataclass(frozen=True, slots=True)
class RuntimeContainer:
    planner: ExecutionPlanner
    executor: Executor
    validator: ResponseValidator
    authorization: AuthorizationService
