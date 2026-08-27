"""
Tool registry.

Maintains the mapping between tool names and registered tool instances.
"""

from __future__ import annotations

from typing import final

from agentic.registry.protocols import ToolRegistryProtocol
from agentic.tools.base import Tool
from core.exceptions.registry import ToolNotFoundError, ToolRegistrationError


@final
class ToolRegistry(ToolRegistryProtocol):
    """
    Registry of AI tools.

    Tools are registered during application startup and resolved
    by their unique tool name at runtime.
    """

    def __init__(
        self,
    ) -> None:
        self._tools: dict[
            str,
            Tool,
        ] = {}

    def register(
        self,
        *,
        component: Tool,
    ) -> None:
        """
        Register a tool.

        Raises:
            ToolRegistrationError:
                If a tool with the same name is already registered.
        """

        name = component.name

        if name in self._tools:
            raise ToolRegistrationError(
                message=(f"Tool '{name}' is already registered."),
            )

        self._tools[name] = component

    def resolve(
        self,
        *,
        key: str,
    ) -> Tool:
        """
        Resolve a tool by name.

        Raises:
            ToolNotFoundError:
                If no registered tool matches the supplied name.
        """

        try:
            return self._tools[key]

        except KeyError as exc:
            raise ToolNotFoundError(
                message=(f"No tool registered with name " f"'{key}'."),
            ) from exc

    def exists(
        self,
        *,
        key: str,
    ) -> bool:
        """
        Return whether a tool is registered.
        """

        return key in self._tools

    def keys(
        self,
    ) -> tuple[str, ...]:
        """
        Return all registered tool names.
        """

        return tuple(
            sorted(
                self._tools,
            ),
        )
