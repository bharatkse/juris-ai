"""
Slack tools.

Same split as email.py: ``slack`` reads a channel and is ungated;
``slack_post`` posts one message and is gated (GATED_TOOLS), running only
with an approval token that covers the exact message. See
tools/messaging/base.py (GatedMCPTool).
"""

from __future__ import annotations

from pydantic import Field

from adapters.observability.logger import get_logger
from agentic.tools.base import Tool, ToolParams
from agentic.tools.messaging.base import GatedMCPTool, MCPMessagingTool

log = get_logger(__name__)

SLACK_SERVER_NAME = "slack"


class SlackParams(ToolParams):
    channel: str = Field(min_length=1, description="The Slack channel to read.")
    limit: int = Field(default=20, ge=1, le=20, description="How many messages to return.")


class SlackPostParams(ToolParams):
    channel: str = Field(min_length=1, max_length=80, description="The Slack channel to post to.")
    text: str = Field(min_length=1, max_length=4000, description="The message text.")


class SlackTool(Tool, MCPMessagingTool):
    """
    Read Slack messages via the Slack MCP server.
    """

    name = "slack"
    description = "Read recent messages from a Slack channel. Does not post."

    params_model = SlackParams

    async def read(self, *, channel: str, limit: int = 20) -> str:
        log.debug("SlackTool.read(channel=%r, limit=%d).", channel, limit)

        return await self._call_mcp(
            server_name=SLACK_SERVER_NAME,
            tool_name="conversations_history",
            arguments={"channel": channel, "limit": limit},
            failure_message="Slack read failed.",
        )

    async def execute(self, *, channel: str, limit: int = 20) -> str:
        return await self.read(channel=channel, limit=limit)


class SlackPostTool(Tool, GatedMCPTool):
    """
    Post one Slack message via the Slack MCP server, only with a valid
    approval.
    """

    name = "slack_post"
    description = (
        "Post a message to a Slack channel. The user reviews and approves "
        "the exact message before it is posted."
    )

    params_model = SlackPostParams

    async def execute(
        self,
        *,
        channel: str,
        text: str,
        approval_token: str = "",
    ) -> str:
        await self._ensure_approved(
            approval_token=approval_token,
            action=self.name,
            payload={"channel": channel, "text": text},
        )

        log.info("Posting approved Slack message to channel=%s.", channel)

        return await self._call_mcp(
            server_name=SLACK_SERVER_NAME,
            tool_name="chat_postMessage",
            arguments={"channel": channel, "text": text},
            failure_message="Slack post failed.",
        )
