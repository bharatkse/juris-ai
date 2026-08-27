"""
MCP client implementation.

Wraps the official MCP Python SDK client session over stdio or
Streamable HTTP transport. One instance per connected server.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from adapters.clients.mcp.base import MCPClient
from adapters.observability.logger import get_logger
from core.dto.clients.mcp import (
    MCPServerConfig,
    MCPToolCallResult,
    MCPToolDescriptor,
    MCPTransport,
)
from core.exceptions.mcp import MCPConnectionError, MCPToolCallError

log = get_logger(__name__)


class MCPClientImpl(MCPClient):
    """
    Concrete MCP client for a single server connection.

    Session lifecycle is explicit: connect() must be called (or the
    instance used as an async context manager) before list_tools() /
    call_tool(), and close() releases the transport.
    """

    def __init__(self, *, config: MCPServerConfig) -> None:
        self._config = config
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        if self._session is not None:
            log.debug("MCP client for '%s' already connected.", self._config.name)
            return

        log.info(
            "Connecting to MCP server '%s' via %s.",
            self._config.name,
            self._config.transport.value,
        )

        try:
            self._exit_stack = AsyncExitStack()

            if self._config.transport is MCPTransport.STDIO:
                if not self._config.command:
                    raise MCPConnectionError(
                        message=f"MCP server '{self._config.name}' is configured "
                        "for stdio transport but has no command."
                    )

                params = StdioServerParameters(
                    command=self._config.command,
                    args=list(self._config.args),
                )
                read, write = await self._exit_stack.enter_async_context(stdio_client(params))
            else:
                if not self._config.url:
                    raise MCPConnectionError(
                        message=f"MCP server '{self._config.name}' is configured "
                        "for streamable_http transport but has no url."
                    )

                read, write, _ = await self._exit_stack.enter_async_context(
                    streamable_http_client(
                        self._config.url,
                        headers=self._config.headers or None,
                    )
                )

            self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()

            log.info("Connected to MCP server '%s'.", self._config.name)

        except MCPConnectionError:
            raise

        except Exception as exc:
            log.exception("Failed to connect to MCP server '%s'.", self._config.name)

            raise MCPConnectionError(
                message=f"Failed to connect to MCP server '{self._config.name}'."
            ) from exc

    async def close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()

        self._session = None
        self._exit_stack = None

        log.info("Closed connection to MCP server '%s'.", self._config.name)

    async def list_tools(self) -> list[MCPToolDescriptor]:
        session = self._require_session()

        result = await session.list_tools()

        return [
            MCPToolDescriptor(
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema,
            )
            for tool in result.tools
        ]

    async def call_tool(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
    ) -> MCPToolCallResult:
        session = self._require_session()

        log.debug(
            "Calling MCP tool '%s' on server '%s'.",
            name,
            self._config.name,
        )

        try:
            result = await session.call_tool(name, arguments=arguments)

        except Exception as exc:
            log.exception(
                "MCP tool call '%s' on server '%s' failed.",
                name,
                self._config.name,
            )

            raise MCPToolCallError(
                message=f"Tool call '{name}' on server " f"'{self._config.name}' failed."
            ) from exc

        content = [block.model_dump() for block in result.content]

        if result.isError:
            log.warning(
                "MCP tool '%s' on server '%s' returned an error result.",
                name,
                self._config.name,
            )

        return MCPToolCallResult(
            tool_name=name,
            server_name=self._config.name,
            is_error=result.isError,
            content=content,
        )

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise MCPConnectionError(
                message=f"MCP client for '{self._config.name}' is not connected. "
                "Call connect() first."
            )

        return self._session

    async def __aenter__(self) -> MCPClientImpl:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
