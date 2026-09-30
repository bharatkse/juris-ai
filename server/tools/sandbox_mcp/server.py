"""
Sandbox messaging MCP server, for the live messaging tests only.

Exposes the two send tools the application calls on its Gmail and Slack
MCP servers, with the same names and inputs, over streamable HTTP:

- ``send_message(to, subject, body)``: relays the message over SMTP
  (``SANDBOX_SMTP_HOST``/``SANDBOX_SMTP_PORT``; Mailpit in the
  ``messaging-test`` compose profile).
- ``chat_postMessage(channel, text)``: posts through the Slack Web API
  with ``SLACK_TEST_BOT_TOKEN``; without a token it returns a
  "not configured" tool error.

Delivery is real; only the MCP server differs from production. Not
imported by the application; it runs as its own process or container
(docs/messaging-live-test.md).

Run on the host: ``python server/tools/sandbox_mcp/server.py`` (listens on
``SANDBOX_MCP_HOST``:``SANDBOX_MCP_PORT``, default 127.0.0.1:8765, path
``/mcp``).
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.message import EmailMessage

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

SLACK_POST_URL = "https://slack.com/api/chat.postMessage"

server = MCPServer(name="juris-ai-sandbox-messaging")


def _smtp_send(*, to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = os.getenv("SANDBOX_MAIL_FROM", "juris-ai-sandbox@example.org")
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    host = os.getenv("SANDBOX_SMTP_HOST", "localhost")
    port = int(os.getenv("SANDBOX_SMTP_PORT", "1025"))

    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.send_message(message)


@server.tool()
async def send_message(to: str, subject: str, body: str) -> str:
    """Send a plain-text email (relayed over SMTP)."""

    try:
        await asyncio.to_thread(_smtp_send, to=to, subject=subject, body=body)
    except (OSError, smtplib.SMTPException) as exc:
        raise ToolError(f"SMTP delivery failed: {exc}") from exc

    return f"Message sent to {to}."


@server.tool(name="chat_postMessage")
async def chat_post_message(channel: str, text: str) -> str:
    """Post a message to a Slack channel (Slack Web API)."""

    token = os.getenv("SLACK_TEST_BOT_TOKEN")
    if not token:
        raise ToolError("Slack is not configured: set SLACK_TEST_BOT_TOKEN for the sandbox server.")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            SLACK_POST_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": text},
        )

    payload = response.json()
    if not payload.get("ok"):
        raise ToolError(f"Slack refused the message: {payload.get('error', response.status_code)}")

    return f"Message posted to {channel} (ts {payload.get('ts')})."


def main() -> None:
    host = os.getenv("SANDBOX_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("SANDBOX_MCP_PORT", "8765"))
    # The tests reach it as localhost:<port>, a container as its service
    # name; neither is a browser, so DNS-rebinding protection only gets
    # in the way here.
    server.run(
        "streamable-http",
        host=host,
        port=port,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


if __name__ == "__main__":
    main()
