"""
AI orchestrator composition.
"""

from __future__ import annotations

from functools import lru_cache

from src.aggregation.response import ResponseAggregator
from src.core.config import get_settings
from src.execution.executor import Executor
from src.orchestration.orchestrator import AIOrchestrator
from src.planning.planner import ExecutionPlanner
from src.runtime.agents import register_agents
from src.runtime.clients import create_clients
from src.runtime.execution import create_executor
from src.runtime.planner import create_planner
from src.runtime.registries import create_registries
from src.runtime.tools import register_tools
from src.validation.response import ResponseValidator


@lru_cache
def get_ai_orchestrator() -> AIOrchestrator:
    """
    Create the AI orchestrator.
    """

    settings = get_settings()

    clients = create_clients(
        settings=settings,
    )

    registries = create_registries()

    register_tools(
        clients=clients,
        registries=registries,
    )

    register_agents(
        clients=clients,
        registries=registries,
    )

    planner: ExecutionPlanner = create_planner(
        clients=clients,
        registries=registries,
    )

    executor: Executor = create_executor(
        registries=registries,
    )

    return AIOrchestrator(
        planner=planner,
        executor=executor,
        validator=ResponseValidator(),
        aggregator=ResponseAggregator(),
    )
