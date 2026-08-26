"""
Runtime dependency containers.

Defines immutable containers used by the runtime composition root to
group shared dependencies during application startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.authorization.service import AuthorizationService
    from src.clients.mcp.registry import MCPServerRegistry
    from src.clients.resolver import LLMResolver
    from src.clients.search_engine.searxng import SearxngClient
    from src.execution.executor import Executor
    from src.execution.validation.response import ResponseValidator
    from src.planning.planner import ExecutionPlanner
    from src.rag.hybrid_retriever import HybridRetriever
    from src.registry.protocols import AgentRegistryProtocol, ToolRegistryProtocol
    from src.tools.search_engine.content_fetch import ContentFetcher


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
