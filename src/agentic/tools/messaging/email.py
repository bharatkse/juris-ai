"""
Email tool.

Read is ungated (same treatment as search tools). Sending is
side-effecting and follows the dry-run -> human approval -> execute
triplet used elsewhere for side-effecting actions (e.g. day-two cloud
operations): draft() builds the preview with no MCP call, send()
only proceeds once an approval token for that exact draft is granted.

execute() intentionally only surfaces read() — this is the entry
point an ordinary agent tool-loop reaches; send() requires an
explicit call with an approval_token and is not reachable through
execute(), so a plain tool-calling loop can never send email
unchecked.
"""

from __future__ import annotations

from dataclasses import dataclass

from adapters.observability.logger import get_logger
from agentic.tools.base import Tool
from agentic.tools.messaging.base import GatedMCPTool

log = get_logger(__name__)

GMAIL_SERVER_NAME = "gmail"


@dataclass(frozen=True, slots=True)
class EmailDraft:
    to: str
    subject: str
    body: str


class EmailTool(Tool, GatedMCPTool):
    """
    Read, draft, and send email via the Gmail MCP server.
    """

    name = "email"
    description = "Read email, and draft/send email (send requires approval)."

    async def read(self, *, query: str, limit: int = 10) -> str:
        log.debug("EmailTool.read(query=%r, limit=%d).", query, limit)

        return await self._call_mcp(
            server_name=GMAIL_SERVER_NAME,
            tool_name="search_messages",
            arguments={"query": query, "max_results": limit},
            failure_message="Email search failed.",
        )

    def draft(self, *, to: str, subject: str, body: str) -> EmailDraft:
        """
        Dry run — builds the draft, makes no MCP call. This is what
        gets shown to the human at the approval step.
        """

        return EmailDraft(to=to, subject=subject, body=body)

    async def send(self, *, draft: EmailDraft, approval_token: str) -> str:
        """
        Execute — only proceeds if the approval token is valid for
        this exact draft. This is the step that must sit behind
        interrupt() in the execution graph.
        """

        await self._ensure_approved(
            approval_token=approval_token,
            action="email.send",
            payload={"to": draft.to, "subject": draft.subject, "body": draft.body},
        )

        log.info("Sending approved email to=%s subject=%r.", draft.to, draft.subject)

        return await self._call_mcp(
            server_name=GMAIL_SERVER_NAME,
            tool_name="send_message",
            arguments={"to": draft.to, "subject": draft.subject, "body": draft.body},
            failure_message="Email send failed.",
        )

    async def execute(self, *, query: str, limit: int = 10) -> str:
        return await self.read(query=query, limit=limit)
