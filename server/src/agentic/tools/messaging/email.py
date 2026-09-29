"""
Email tools.

``email`` reads mail and is ungated (same treatment as search tools).
``email_send`` sends one email and is gated: it is in GATED_TOOLS, so an
agent's call pauses for human approval, and the parameters the agent
proposed are the draft the human reviews (and may edit). After approval,
the resume path runs the tool with the approval id as its token, and the
tool sends only if the token covers this exact draft (see
tools/messaging/base.py, GatedMCPTool).
"""

from __future__ import annotations

from pydantic import Field

from adapters.observability.logger import get_logger
from agentic.tools.base import Tool, ToolParams
from agentic.tools.messaging.base import GatedMCPTool, MCPMessagingTool

log = get_logger(__name__)

GMAIL_SERVER_NAME = "gmail"

# Deliberately loose (one "@", a dot in the domain, no whitespace) and a
# plain str, not EmailStr: the approved draft is compared to the sent one
# field by field, so the address must not be normalized in between.
_EMAIL_ADDRESS = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class EmailParams(ToolParams):
    query: str = Field(min_length=1, description="Which emails to read (mail search query).")
    limit: int = Field(default=10, ge=1, le=20, description="How many emails to return.")


class EmailSendParams(ToolParams):
    to: str = Field(
        pattern=_EMAIL_ADDRESS,
        max_length=254,
        description="Recipient email address.",
    )
    subject: str = Field(min_length=1, max_length=200, description="Subject line.")
    body: str = Field(min_length=1, max_length=10000, description="Plain-text message body.")


class EmailTool(Tool, MCPMessagingTool):
    """
    Read email via the Gmail MCP server.
    """

    name = "email"
    description = "Search and read the user's email. Does not send."

    params_model = EmailParams

    async def read(self, *, query: str, limit: int = 10) -> str:
        log.debug("EmailTool.read(limit=%d, query_length=%d).", limit, len(query))

        return await self._call_mcp(
            server_name=GMAIL_SERVER_NAME,
            tool_name="search_messages",
            arguments={"query": query, "max_results": limit},
            failure_message="Email search failed.",
        )

    async def execute(self, *, query: str, limit: int = 10) -> str:
        return await self.read(query=query, limit=limit)


class EmailSendTool(Tool, GatedMCPTool):
    """
    Send one email via the Gmail MCP server, only with a valid approval.
    """

    name = "email_send"
    description = (
        "Send an email. The user reviews and approves the exact message " "before it is sent."
    )

    params_model = EmailSendParams

    async def execute(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        approval_token: str = "",
    ) -> str:
        await self._ensure_approved(
            approval_token=approval_token,
            action=self.name,
            payload={"to": to, "subject": subject, "body": body},
        )

        log.info("Sending approved email to=%s.", to)

        return await self._call_mcp(
            server_name=GMAIL_SERVER_NAME,
            tool_name="send_message",
            arguments={"to": to, "subject": subject, "body": body},
            failure_message="Email send failed.",
        )
