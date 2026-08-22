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
    from src.clients.llm.base import LLMClient
    from src.clients.web_search.base import WebSearchClient
    from src.execution.executor import Executor
    from src.execution.validation.response import ResponseValidator
    from src.planning.planner import ExecutionPlanner
    from src.registry.protocols import AgentRegistryProtocol, ToolRegistryProtocol


@dataclass(frozen=True, slots=True)
class ClientContainer:
    llm_client: LLMClient
    web_search_client: WebSearchClient


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
