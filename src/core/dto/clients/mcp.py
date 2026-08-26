"""
MCP client DTOs.

Internal cross-layer transfer objects for MCP tool discovery and
invocation. Dataclasses, per the project's convention: Pydantic is
reserved for validation boundaries (api/schemas, core/schemas).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MCPTransport(str, Enum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    """
    Connection configuration for a single MCP server.
    """

    name: str
    transport: MCPTransport
    # stdio
    command: str | None = None
    args: tuple[str, ...] = field(default_factory=tuple)
    # streamable http
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MCPToolDescriptor:
    """
    A tool exposed by an MCP server, as returned by list_tools().
    """

    name: str
    description: str | None
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MCPToolCallResult:
    """
    Result of a single tool invocation.
    """

    tool_name: str
    server_name: str
    is_error: bool
    content: list[dict[str, Any]]

    def as_text(self) -> str:
        """
        Concatenate all text-typed content blocks.

        Convenience for the common case where a tool returns a single
        text block (e.g. search/retrieve results already formatted as
        a string by the server).
        """

        parts = [block.get("text", "") for block in self.content if block.get("type") == "text"]

        return "\n".join(parts)
