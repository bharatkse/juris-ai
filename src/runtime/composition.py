"""
AI orchestrator composition.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver

from src.core.config import get_settings
from src.execution.aggregation.response import ResponseAggregator
from src.execution.validation.response import ResponseValidator
from src.observability.langsmith import configure_langsmith
from src.orchestration.orchestrator import AIOrchestrator
from src.runtime.factories.agents import register_agents
from src.runtime.factories.authorization import create_authorization
from src.runtime.factories.clients import create_clients
from src.runtime.factories.executor import create_executor
from src.runtime.factories.planner import create_planner
from src.runtime.factories.registries import create_registries
from src.runtime.factories.tools import register_tools


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
