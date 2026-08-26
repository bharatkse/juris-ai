"""
MCP server registry.

Resolves the configured MCP client for a given server name. Mirrors
the shape of clients/resolver.py (LLMResolver) intentionally — same
resolution pattern, different domain.

Sessions are connect-per-call by default: each call_tool() acquires a
fresh connection via an async context manager and releases it
immediately after. This keeps Execution State simple (no long-lived
session to track per request) at the cost of reconnect overhead per
call. Revisit with a pooled/long-lived session if that overhead proves
significant under load.
"""

from __future__ import annotations

from src.clients.mcp.base import MCPClient
from src.clients.mcp.client import MCPClientImpl
from src.core.dto.clients.mcp import MCPServerConfig, MCPToolCallResult
from src.core.exceptions.mcp import MCPServerNotConfiguredError
from src.core.logger import get_logger

log = get_logger(__name__)


class MCPServerRegistry:
    """
    Registry of configured MCP servers.
    """

    def __init__(self, *, servers: dict[str, MCPServerConfig]) -> None:
        self._servers = servers

        log.info(
            "Initialized MCP server registry with %d server(s): %s.",
            len(servers),
            ", ".join(servers.keys()),
        )

    def get_config(self, *, server_name: str) -> MCPServerConfig:
        try:
            return self._servers[server_name]

        except KeyError as exc:
            log.exception("MCP server '%s' is not configured.", server_name)

            raise MCPServerNotConfiguredError(
                message=f"MCP server '{server_name}' is not configured."
            ) from exc

    def client_for(self, *, server_name: str) -> MCPClient:
        """
        Build a new (unconnected) client for the given server.

        Callers should use this as an async context manager:

            async with registry.client_for(server_name="rag-server") as client:
                result = await client.call_tool(name="retrieve", arguments={...})
        """

        config = self.get_config(server_name=server_name)

        return MCPClientImpl(config=config)

    async def call_tool(
        self,
        *,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> MCPToolCallResult:
        """
        Convenience one-shot call: connect, invoke, disconnect.
        """

        async with self.client_for(server_name=server_name) as client:
            return await client.call_tool(name=tool_name, arguments=arguments)

    def supports(self, *, server_name: str) -> bool:
        return server_name in self._servers
