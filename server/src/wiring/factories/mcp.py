"""
MCP registry composition.

Builds the MCPServerRegistry from configured server connection
settings. Add a new MCP server by adding one entry here plus its
corresponding settings fields — no other runtime wiring changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.clients.mcp.registry import MCPServerRegistry
from core.dto.clients.mcp import MCPServerConfig, MCPTransport

if TYPE_CHECKING:
    from config.settings import Settings


def build_mcp_registry(*, settings: Settings) -> MCPServerRegistry:
    urls = {
        "rag-server": settings.llm.mcp_rag_server_url,
        # Names must match GMAIL_SERVER_NAME / SLACK_SERVER_NAME in
        # agentic/tools/messaging/. Registered only when configured.
        "gmail": settings.llm.MCP_GMAIL_SERVER_URL,
        "slack": settings.llm.MCP_SLACK_SERVER_URL,
    }

    return MCPServerRegistry(
        servers={
            name: MCPServerConfig(
                name=name,
                transport=MCPTransport.STREAMABLE_HTTP,
                url=url,
            )
            for name, url in urls.items()
            if url
        }
    )
