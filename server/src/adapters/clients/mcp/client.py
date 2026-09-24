"""
MCP client implementation.

Wraps the official MCP Python SDK client session over stdio or
Streamable HTTP transport. One instance per connected server.
"""

from __future__ import annotations

from contextlib import AsyncExitStack, suppress
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

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

                # mcp>=2 takes headers via a caller-owned HTTP client, not
                # a headers= argument. create_mcp_http_client keeps the
                # SDK's default transport timeouts; a client we pass in is
                # ours to close, hence entering it on the exit stack.
                http_client = None
                if self._config.headers:
                    http_client = await self._exit_stack.enter_async_context(
                        create_mcp_http_client(headers=dict(self._config.headers))
                    )

                read, write = await self._exit_stack.enter_async_context(
                    streamable_http_client(self._config.url, http_client=http_client)
                )

            self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()

            log.info("Connected to MCP server '%s'.", self._config.name)

        except MCPConnectionError:
            await self._discard_partial_connection()
            raise

        except Exception as exc:
            log.exception("Failed to connect to MCP server '%s'.", self._config.name)
            await self._discard_partial_connection()

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
                input_schema=tool.input_schema,
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

        if result.is_error:
            log.warning(
                "MCP tool '%s' on server '%s' returned an error result.",
                name,
                self._config.name,
            )

        return MCPToolCallResult(
            tool_name=name,
            server_name=self._config.name,
            is_error=result.is_error,
            content=content,
        )

    async def _discard_partial_connection(self) -> None:
        """
        Release whatever connect() entered before failing -- e.g. a
        spawned stdio server process and its transport task group --
        so a failed connect doesn't leak them (a leaked stdio transport
        also keeps the event loop from shutting down). Cleanup errors
        are suppressed so the original connect failure is what surfaces.
        """

        exit_stack, self._exit_stack, self._session = self._exit_stack, None, None

        if exit_stack is not None:
            with suppress(Exception):
                await exit_stack.aclose()

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
