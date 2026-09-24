"""
MCP client interface.

Defines the contract for calling tools and reading resources exposed by
an MCP server. Concrete implementations wrap the official MCP Python SDK
client session over a specific transport (stdio, Streamable HTTP).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.dto.clients.mcp import MCPToolCallResult, MCPToolDescriptor


class MCPClient(ABC):
    """
    Abstract MCP client.

    One instance represents a connection to a single MCP server.
    """

    @abstractmethod
    async def list_tools(self) -> list[MCPToolDescriptor]:
        """
        Return the tools exposed by the connected server.
        """
        raise NotImplementedError

    @abstractmethod
    async def call_tool(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
    ) -> MCPToolCallResult:
        """
        Invoke a tool on the connected server.

        Args:
            name: Tool name as exposed by the server.
            arguments: Tool arguments, validated against the tool's schema
                by the server itself.

        Returns:
            Parsed tool call result.

        Raises:
            MCPToolCallError: If the server returns an error or the
                connection fails.
        """
        raise NotImplementedError

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish the underlying transport connection.
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """
        Tear down the underlying transport connection.
        """
        raise NotImplementedError

    @abstractmethod
    async def __aenter__(self) -> MCPClient:
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, *exc_info: object) -> None:
        raise NotImplementedError
