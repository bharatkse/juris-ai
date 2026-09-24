"""
Tests for MCPClientImpl against a real MCP server over stdio.

Uses the installed MCP SDK end to end (no mocks), so SDK API drift --
e.g. mcp 2.x renaming Tool.inputSchema -> input_schema and
CallToolResult.isError -> is_error -- fails here instead of silently
turning every connect into an MCPConnectionError.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from adapters.clients.mcp.client import MCPClientImpl
from core.dto.clients.mcp import MCPServerConfig, MCPTransport
from core.exceptions.mcp import MCPConnectionError

PROBE_SERVER = Path(__file__).with_name("_probe_server.py")


def _stdio_config() -> MCPServerConfig:
    return MCPServerConfig(
        name="probe",
        transport=MCPTransport.STDIO,
        command=sys.executable,
        args=(str(PROBE_SERVER),),
    )


async def test_lists_tools_with_input_schema() -> None:
    async with MCPClientImpl(config=_stdio_config()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert set(tools) == {"add", "boom"}
    assert set(tools["add"].input_schema["properties"]) == {"a", "b"}


async def test_call_tool_returns_content() -> None:
    async with MCPClientImpl(config=_stdio_config()) as client:
        result = await client.call_tool(name="add", arguments={"a": 2, "b": 3})

    assert result.is_error is False
    assert result.content[0]["text"] == "5"


async def test_call_tool_reports_tool_errors() -> None:
    async with MCPClientImpl(config=_stdio_config()) as client:
        result = await client.call_tool(name="boom", arguments={})

    assert result.is_error is True


async def test_call_before_connect_raises() -> None:
    client = MCPClientImpl(config=_stdio_config())

    with pytest.raises(MCPConnectionError):
        await client.list_tools()


async def test_failed_connect_raises_and_releases_transport() -> None:
    # A stdio "server" that exits immediately: initialize() fails. The
    # client must raise MCPConnectionError and tear the half-open
    # transport down rather than leaking it (which hangs the loop).
    config = MCPServerConfig(
        name="not-a-server",
        transport=MCPTransport.STDIO,
        command=sys.executable,
        args=("-c", "pass"),
    )
    client = MCPClientImpl(config=config)

    with pytest.raises(MCPConnectionError):
        await asyncio.wait_for(client.connect(), timeout=30)

    with pytest.raises(MCPConnectionError):
        await client.list_tools()
