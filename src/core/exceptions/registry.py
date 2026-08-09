"""
Registry exceptions.

Registry exceptions are raised while registering or resolving agents
and tools within the AI runtime.

These exceptions inherit from ``AIError`` and indicate failures in
runtime component discovery or registration.
"""

from __future__ import annotations

from src.core.constants import (
    ERROR_AGENT_NOT_FOUND,
    ERROR_AGENT_REGISTRATION,
    ERROR_REGISTRY,
    ERROR_TOOL_NOT_FOUND,
    ERROR_TOOL_REGISTRATION,
)
from src.core.exceptions.base import AIError


class RegistryError(AIError):
    """
    Base exception for registry failures.
    """

    error_code = ERROR_REGISTRY
    default_message = "Registry operation failed."


class AgentRegistrationError(RegistryError):
    """
    Raised when an agent cannot be registered.

    Examples:
        - Duplicate capability registration
        - Duplicate agent registration
        - Invalid agent configuration
    """

    error_code = ERROR_AGENT_REGISTRATION
    default_message = "Agent registration failed."


class AgentNotFoundError(RegistryError):
    """
    Raised when no registered agent supports the requested capability.

    Examples:
        - Unknown capability
        - Agent not registered
    """

    error_code = ERROR_AGENT_NOT_FOUND
    default_message = "No suitable agent found."


class ToolRegistrationError(RegistryError):
    """
    Raised when a tool cannot be registered.

    Examples:
        - Duplicate tool registration
        - Invalid tool configuration
    """

    error_code = ERROR_TOOL_REGISTRATION
    default_message = "Tool registration failed."


class ToolNotFoundError(RegistryError):
    """
    Raised when a requested tool is not registered.

    Examples:
        - Unknown tool
        - Tool unavailable
    """

    error_code = ERROR_TOOL_NOT_FOUND
    default_message = "Requested tool not found."
