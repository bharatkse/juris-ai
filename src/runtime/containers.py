"""
Runtime dependency containers.

Defines immutable containers used by the runtime composition root to
group shared dependencies during application startup.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.clients.llm.base import LLMClient
from src.clients.web_search.base import WebSearchClient
from src.execution.executor import Executor
from src.planning.planner import ExecutionPlanner
from src.registry.protocols import AgentRegistryProtocol, ToolRegistryProtocol
from src.validation.response import ResponseValidator


@dataclass(frozen=True, slots=True)
class ClientContainer:
    """
    Shared external service clients.
    """

    llm_client: LLMClient

    web_search_client: WebSearchClient


@dataclass(frozen=True, slots=True)
class RegistryContainer:
    """
    Runtime registries.
    """

    agent_registry: AgentRegistryProtocol

    tool_registry: ToolRegistryProtocol


@dataclass(frozen=True, slots=True)
class RuntimeContainer:
    """
    Core runtime services.
    """

    planner: ExecutionPlanner

    executor: Executor

    validator: ResponseValidator
