"""
AI orchestrator composition.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver

from adapters.observability.langsmith import configure_langsmith
from agentic.execution.aggregation.response import ResponseAggregator
from agentic.execution.validation.response import ResponseValidator
from agentic.orchestration.orchestrator import AIOrchestrator
from agentic.runtime.factories.agents import register_agents
from agentic.runtime.factories.authorization import create_authorization
from agentic.runtime.factories.clients import create_clients
from agentic.runtime.factories.executor import create_executor
from agentic.runtime.factories.planner import create_planner
from agentic.runtime.factories.registries import create_registries
from agentic.runtime.factories.tools import register_tools
from config.settings import get_settings


def create_ai_orchestrator(
    *,
    checkpointer: BaseCheckpointSaver,
) -> AIOrchestrator:
    """
    Create the AI orchestrator with its runtime dependencies.
    """

    settings = get_settings()
    configure_langsmith(settings=settings)

    authorization = create_authorization()

    clients = create_clients(settings=settings)
    registries = create_registries()

    register_tools(clients=clients, registries=registries, approval_service=authorization)
    register_agents(clients=clients, registries=registries)

    return AIOrchestrator(
        planner=create_planner(clients=clients),
        executor=create_executor(registries=registries, checkpointer=checkpointer),
        validator=ResponseValidator(),
        aggregator=ResponseAggregator(),
        authorization=authorization,
    )
