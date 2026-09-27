"""
Tool registry.

Maintains the mapping between tool names and registered tool instances.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, final

from agentic.registry.protocols import ToolRegistryProtocol
from agentic.tools.base import Tool
from core.dto.tool import ToolSpecDTO
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

    def describe(
        self,
        *,
        names: Iterable[str],
    ) -> tuple[ToolSpecDTO, ...]:
        """
        Describe the named tools for an agent's prompt, sorted by name.

        Only tools that are registered and callable by an agent (they
        declare a params_model) are included: a name a policy grants but
        nothing registers, or a server-side-only tool, is left out rather
        than offered to the model.
        """

        specs: list[ToolSpecDTO] = []

        for name in sorted(set(names)):
            tool = self._tools.get(name)

            if tool is None or tool.params_model is None:
                continue

            specs.append(
                ToolSpecDTO(
                    name=tool.name,
                    description=tool.description,
                    parameters_schema=_without_titles(
                        tool.params_model.model_json_schema(),
                    ),
                ),
            )

        return tuple(specs)

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


def _without_titles(schema: Any) -> Any:
    """
    Drop pydantic's generated "title" keys: they repeat the field names
    and only add prompt tokens.
    """

    if isinstance(schema, dict):
        return {
            key: _without_titles(value)
            for key, value in schema.items()
            if not (key == "title" and isinstance(value, str))
        }

    if isinstance(schema, list):
        return [_without_titles(item) for item in schema]

    return schema
