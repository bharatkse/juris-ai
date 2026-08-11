"""
Runtime registry composition.

Creates the shared registries used by the AI runtime.

Responsibilities:

- Create the agent registry
- Create the tool registry

No business logic belongs in this module.
"""

from __future__ import annotations

from src.registry.agent import AgentRegistry
from src.registry.tool import ToolRegistry
from src.runtime.containers import RegistryContainer


def create_registries() -> RegistryContainer:
    """
    Create shared runtime registries.

    Registries are created once during application startup and
    reused for the lifetime of the application.
    """

    return RegistryContainer(
        agent_registry=AgentRegistry(),
        tool_registry=ToolRegistry(),
    )
