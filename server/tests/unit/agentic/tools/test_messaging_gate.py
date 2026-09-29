"""
Messaging tools: reading is ungated; sending is a separate, gated tool
that reaches the MCP server only with an approval token its verifier
accepts for the exact payload.

Before this split, email/slack were one tool each whose execute() was the
read path, so an "approved send" ran a mail search and nothing was ever
sent (review S4).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.registry.tool import ToolRegistry
from agentic.tools.constants import GATED_TOOLS
from agentic.tools.messaging.base import DenyAllApprovalVerifier
from agentic.tools.messaging.email import EmailSendTool, EmailTool
from agentic.tools.messaging.slack import SlackPostTool, SlackTool
from agentic.tools.runtime.invocation import ToolExecutionService
from core.dto.clients.mcp import MCPToolCallResult

DRAFT = {"to": "client@example.org", "subject": "Notice", "body": "Please sign."}
TOKEN = "appr_" + "a" * 32


def _mcp_registry() -> MagicMock:
    registry = MagicMock()
    registry.call_tool = AsyncMock(
        side_effect=lambda *, server_name, tool_name, arguments: MCPToolCallResult(
            tool_name=tool_name,
            server_name=server_name,
            is_error=False,
            content=[{"type": "text", "text": f"{tool_name} ok"}],
        )
    )
    return registry


class ExactPayloadVerifier:
    """Approves TOKEN for one tool and one payload only."""

    def __init__(self, *, action: str, payload: dict) -> None:
        self.action = action
        self.payload = payload

    async def is_approved(self, *, token: str, action: str, payload: dict) -> bool:
        return token == TOKEN and action == self.action and payload == self.payload


def test_only_the_send_tools_are_gated() -> None:
    assert GATED_TOOLS == frozenset({"email_send", "slack_post"})


async def test_email_read_tool_only_searches() -> None:
    registry = _mcp_registry()

    await EmailTool(mcp_registry=registry).execute(query="case 84021", limit=5)

    registry.call_tool.assert_awaited_once_with(
        server_name="gmail",
        tool_name="search_messages",
        arguments={"query": "case 84021", "max_results": 5},
    )


async def test_slack_read_tool_only_reads() -> None:
    registry = _mcp_registry()

    await SlackTool(mcp_registry=registry).execute(channel="#legal")

    assert registry.call_tool.await_args.kwargs["tool_name"] == "conversations_history"


@pytest.mark.parametrize("token", ["", "any-token", TOKEN])
async def test_email_send_is_denied_without_reaching_mcp(token: str) -> None:
    registry = _mcp_registry()
    tool = EmailSendTool(mcp_registry=registry, approval_service=DenyAllApprovalVerifier())

    with pytest.raises(PermissionError):
        await tool.execute(**DRAFT, approval_token=token)

    registry.call_tool.assert_not_awaited()


async def test_slack_post_is_denied_without_reaching_mcp() -> None:
    registry = _mcp_registry()
    tool = SlackPostTool(mcp_registry=registry, approval_service=DenyAllApprovalVerifier())

    with pytest.raises(PermissionError):
        await tool.execute(channel="#legal", text="hi", approval_token=TOKEN)

    registry.call_tool.assert_not_awaited()


async def test_approved_email_is_sent_exactly_as_approved() -> None:
    registry = _mcp_registry()
    tool = EmailSendTool(
        mcp_registry=registry,
        approval_service=ExactPayloadVerifier(action="email_send", payload=DRAFT),
    )

    result = await tool.execute(**DRAFT, approval_token=TOKEN)

    assert result == "send_message ok"
    registry.call_tool.assert_awaited_once_with(
        server_name="gmail",
        tool_name="send_message",
        arguments=DRAFT,
    )


async def test_approved_slack_message_is_posted() -> None:
    registry = _mcp_registry()
    message = {"channel": "#legal", "text": "Filed."}
    tool = SlackPostTool(
        mcp_registry=registry,
        approval_service=ExactPayloadVerifier(action="slack_post", payload=message),
    )

    await tool.execute(**message, approval_token=TOKEN)

    registry.call_tool.assert_awaited_once_with(
        server_name="slack",
        tool_name="chat_postMessage",
        arguments=message,
    )


async def test_a_changed_draft_is_not_sent() -> None:
    registry = _mcp_registry()
    tool = EmailSendTool(
        mcp_registry=registry,
        approval_service=ExactPayloadVerifier(action="email_send", payload=DRAFT),
    )

    with pytest.raises(PermissionError):
        await tool.execute(**{**DRAFT, "to": "attacker@example.org"}, approval_token=TOKEN)

    registry.call_tool.assert_not_awaited()


def _service(registry: MagicMock, verifier) -> ToolExecutionService:
    tools = ToolRegistry()
    tools.register(component=EmailSendTool(mcp_registry=registry, approval_service=verifier))
    return ToolExecutionService(tool_registry=tools)


async def test_execution_service_passes_the_approval_token_to_a_send_tool() -> None:
    registry = _mcp_registry()
    service = _service(registry, ExactPayloadVerifier(action="email_send", payload=DRAFT))

    result = await service.execute(tool_name="email_send", parameters=DRAFT, approval_token=TOKEN)

    assert result.success is True
    registry.call_tool.assert_awaited_once()


async def test_an_ordinary_call_to_a_send_tool_sends_nothing() -> None:
    """
    Without the resume path's token (e.g. a call that bypassed the gate),
    the send tool refuses and the MCP server is never reached.
    """

    registry = _mcp_registry()
    service = _service(registry, ExactPayloadVerifier(action="email_send", payload=DRAFT))

    result = await service.execute(tool_name="email_send", parameters=DRAFT)

    assert result.success is False
    registry.call_tool.assert_not_awaited()


async def test_the_model_cannot_supply_its_own_approval_token() -> None:
    registry = _mcp_registry()
    service = _service(registry, ExactPayloadVerifier(action="email_send", payload=DRAFT))

    result = await service.execute(
        tool_name="email_send",
        parameters={**DRAFT, "approval_token": TOKEN},
    )

    assert result.success is False
    assert result.execution_metadata["error_type"] == "InvalidParameters"
    registry.call_tool.assert_not_awaited()


@pytest.mark.parametrize(
    "parameters",
    [
        {**DRAFT, "to": "not-an-address"},
        {**DRAFT, "subject": ""},
        {"to": DRAFT["to"], "subject": "Notice"},
    ],
)
def test_check_parameters_rejects_a_malformed_draft(parameters: dict) -> None:
    service = _service(_mcp_registry(), DenyAllApprovalVerifier())

    result = service.check_parameters(tool_name="email_send", parameters=parameters)

    assert result is not None
    assert result.execution_metadata["error_type"] == "InvalidParameters"


def test_check_parameters_accepts_a_valid_draft() -> None:
    service = _service(_mcp_registry(), DenyAllApprovalVerifier())

    assert service.check_parameters(tool_name="email_send", parameters=DRAFT) is None
