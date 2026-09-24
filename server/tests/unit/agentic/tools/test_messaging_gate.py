"""
Gated messaging actions (email.send / slack.post) with the production
wiring's DenyAllApprovalVerifier: denied, and the MCP server is never
called.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agentic.tools.messaging.base import DenyAllApprovalVerifier
from agentic.tools.messaging.email import EmailDraft, EmailTool
from agentic.tools.messaging.slack import SlackDraft, SlackTool


async def test_email_send_is_denied_without_reaching_mcp() -> None:
    registry = MagicMock()
    tool = EmailTool(mcp_registry=registry, approval_service=DenyAllApprovalVerifier())

    with pytest.raises(PermissionError):
        await tool.send(
            draft=EmailDraft(to="a@example.org", subject="s", body="b"),
            approval_token="any-token",
        )

    registry.assert_not_called()
    assert registry.method_calls == []


async def test_slack_post_is_denied_without_reaching_mcp() -> None:
    registry = MagicMock()
    tool = SlackTool(mcp_registry=registry, approval_service=DenyAllApprovalVerifier())

    with pytest.raises(PermissionError):
        await tool.post(draft=SlackDraft(channel="#c", text="t"), approval_token="any-token")

    assert registry.method_calls == []
