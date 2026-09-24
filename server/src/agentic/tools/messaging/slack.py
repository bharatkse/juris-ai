"""
Slack tool.

Same pattern as email.py: read is ungated, posting is gated behind
the dry-run -> approval -> execute triplet. See
tools/messaging/base.py (GatedMCPTool) for the shared machinery.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field

from adapters.observability.logger import get_logger
from agentic.tools.base import Tool, ToolParams
from agentic.tools.messaging.base import GatedMCPTool

log = get_logger(__name__)

SLACK_SERVER_NAME = "slack"


@dataclass(frozen=True, slots=True)
class SlackDraft:
    channel: str
    text: str


class SlackParams(ToolParams):
    channel: str = Field(min_length=1, description="The Slack channel to read.")
    limit: int = Field(default=20, ge=1, le=20, description="How many messages to return.")


class SlackTool(Tool, GatedMCPTool):
    """
    Read, draft, and post Slack messages via the Slack MCP server.
    """

    name = "slack"
    description = "Read Slack messages, and draft/post messages (posting requires approval)."

    params_model = SlackParams

    async def read(self, *, channel: str, limit: int = 20) -> str:
        log.debug("SlackTool.read(channel=%r, limit=%d).", channel, limit)

        return await self._call_mcp(
            server_name=SLACK_SERVER_NAME,
            tool_name="conversations_history",
            arguments={"channel": channel, "limit": limit},
            failure_message="Slack read failed.",
        )

    def draft(self, *, channel: str, text: str) -> SlackDraft:
        return SlackDraft(channel=channel, text=text)

    async def post(self, *, draft: SlackDraft, approval_token: str) -> str:
        await self._ensure_approved(
            approval_token=approval_token,
            action="slack.post",
            payload={"channel": draft.channel, "text": draft.text},
        )

        log.info("Posting approved Slack message to channel=%s.", draft.channel)

        return await self._call_mcp(
            server_name=SLACK_SERVER_NAME,
            tool_name="chat_postMessage",
            arguments={"channel": draft.channel, "text": draft.text},
            failure_message="Slack post failed.",
        )

    async def execute(self, *, channel: str, limit: int = 20) -> str:
        return await self.read(channel=channel, limit=limit)
