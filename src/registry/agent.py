"""
Agent registry.

Maintains the mapping between agent capabilities and registered
agent instances.
"""

from __future__ import annotations

from typing import final

from src.agents.base import BaseAgent
from src.core.exceptions.registry import AgentNotFoundError, AgentRegistrationError
from src.registry.protocols import AgentRegistryProtocol


@final
class AgentRegistry(AgentRegistryProtocol):
    """
    Registry of AI agents.

    Agents are registered during application startup and resolved
    by capability at runtime.
    """

    def __init__(
        self,
    ) -> None:
        self._agents: dict[
            str,
            BaseAgent,
        ] = {}

    def register(
        self,
        *,
        component: BaseAgent,
    ) -> None:
        """
        Register an agent.

        Raises:
            AgentRegistrationError:
                If a capability is already registered.
        """

        for capability in component.metadata.capabilities:
            if capability in self._agents:
                existing = self._agents[capability]

                raise AgentRegistrationError(
                    message=(
                        f"Capability '{capability}' is already "
                        f"registered by '{existing.metadata.name}'."
                    ),
                )

            self._agents[capability] = component

    def resolve(
        self,
        *,
        key: str,
    ) -> BaseAgent:
        """
        Resolve an agent by capability.

        Raises:
            AgentNotFoundError:
                If no registered agent supports the supplied capability.
        """

        try:
            return self._agents[key]

        except KeyError as exc:
            raise AgentNotFoundError(
                message=(f"No agent registered for capability " f"'{key}'."),
            ) from exc

    def exists(
        self,
        *,
        key: str,
    ) -> bool:
        """
        Return whether a capability is registered.
        """

        return key in self._agents

    def keys(
        self,
    ) -> tuple[str, ...]:
        """
        Return all registered capabilities.
        """

        return tuple(
            sorted(
                self._agents,
            ),
        )
