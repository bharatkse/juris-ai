"""
Tool exceptions.

Tool exceptions are raised during tool execution.

These exceptions inherit from ``AIError`` and indicate failures
that occur while executing a tool requested by an agent.

Tool lifecycle:

Agent
    │
    ▼
ToolRegistry
    │
    ▼
Tool.execute()
    │
    ├── Validate Input
    ├── Execute Operation
    └── Return Result
"""

from __future__ import annotations

from core.constants import (
    ERROR_TOOL,
    ERROR_TOOL_CONFIGURATION,
    ERROR_TOOL_EXECUTION,
    ERROR_TOOL_VALIDATION,
)
from core.exceptions.base import AIError


class ToolError(AIError):
    """
    Base exception for tool failures.
    """

    error_code = ERROR_TOOL
    default_message = "Tool operation failed."


class ToolExecutionError(ToolError):
    """
    Raised when a tool fails during execution.

    Examples:
        - Search failed
        - Retriever failed
        - Parser failed
        - Database query failed
    """

    error_code = ERROR_TOOL_EXECUTION
    default_message = "Tool execution failed."


class ToolValidationError(ToolError):
    """
    Raised when a tool receives invalid input.

    Examples:
        - Missing required parameters
        - Invalid tool arguments
        - Unsupported input format
    """

    error_code = ERROR_TOOL_VALIDATION
    default_message = "Tool validation failed."


class ToolConfigurationError(ToolError):
    """
    Raised when a tool is incorrectly configured.

    Examples:
        - Missing API key
        - Invalid endpoint configuration
        - Missing dependency
    """

    error_code = ERROR_TOOL_CONFIGURATION
    default_message = "Tool configuration is invalid."
