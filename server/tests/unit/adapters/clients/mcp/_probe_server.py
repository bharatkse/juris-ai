"""
Minimal real MCP server (stdio) used by test_client.py -- not a test
module itself (no test_ prefix), launched as a subprocess.
"""

from mcp.server.mcpserver import MCPServer

server = MCPServer("probe")


@server.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@server.tool()
def boom() -> str:
    """Always fails."""
    raise ValueError("boom")


if __name__ == "__main__":
    server.run()
