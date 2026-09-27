"""
MCP client exceptions.
"""

from __future__ import annotations

from core.exceptions.base import AppError


class MCPError(AppError):
    """
    Base exception for all MCP-related failures.
    """


class MCPServerNotConfiguredError(MCPError):
    """
    Raised when resolving an MCP server name that has no registered
    configuration.
    """


class MCPConnectionError(MCPError):
    """
    Raised when a transport-level connection to an MCP server fails.
    """


class MCPToolCallError(MCPError):
    """
    Raised when a tool invocation fails or the server returns an
    error result.
    """
