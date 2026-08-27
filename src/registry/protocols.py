"""
Registry protocols.

Defines the contracts for registry implementations used throughout the
AI runtime.

A registry is responsible for:

- Registering runtime components
- Resolving registered components
- Querying registration state

A registry is NOT responsible for:

- Creating components
- Managing component lifecycle
- Executing components
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from src.agents.base import BaseAgent
from src.clients.llm.base import LLMClient
from src.tools.base import Tool

T = TypeVar("T")


@runtime_checkable
class Registry(Protocol[T]):
    """
    Generic registry contract.
    """

    def register(
        self,
        *,
        component: T,
    ) -> None:
        """
        Register a runtime component.

        Raises:
            RegistryError:
                If the component cannot be registered.
        """
        ...

    def resolve(
        self,
        *,
        key: str,
    ) -> T:
        """
        Resolve a registered component.

        Raises:
            RegistryError:
                If the supplied key is unknown.
        """
        ...

    def exists(
        self,
        *,
        key: str,
    ) -> bool:
        """
        Return whether the supplied key is registered.
        """
        ...

    def keys(
        self,
    ) -> tuple[str, ...]:
        """
        Return all registered keys.

        The returned tuple is immutable and ordered
        deterministically.
        """
        ...


@runtime_checkable
class AgentRegistryProtocol(
    Registry[BaseAgent],
    Protocol,
):
    """
    Registry contract for AI agents.

    Agents are registered by capability and resolved
    by capability at runtime.
    """

    ...


@runtime_checkable
class ToolRegistryProtocol(
    Registry[Tool],
    Protocol,
):
    """
    Registry contract for AI tools.

    Tools are registered and resolved by their
    unique tool name.
    """

    ...


@runtime_checkable
class LLMClientRegistryProtocol(
    Registry[LLMClient],
    Protocol,
):
    """
    Registry contract for LLM clients.

    LLM clients are registered by logical runtime key
    and resolved when constructing AI components.
    """

    ...
