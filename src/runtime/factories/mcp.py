"""
MCP registry composition.

Builds the MCPServerRegistry from configured server connection
settings. Add a new MCP server by adding one entry here plus its
corresponding settings fields — no other runtime wiring changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.clients.mcp.registry import MCPServerRegistry
from src.core.dto.clients.mcp import MCPServerConfig, MCPTransport

if TYPE_CHECKING:
    from src.core.config import Settings


def build_mcp_registry(*, settings: Settings) -> MCPServerRegistry:
    return MCPServerRegistry(
        servers={
            "rag-server": MCPServerConfig(
                name="rag-server",
                transport=MCPTransport.STREAMABLE_HTTP,
                url=settings.mcp_rag_server_url,
            ),
        }
    )
