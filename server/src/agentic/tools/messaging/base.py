"""
Shared base for gated messaging tools.

Reading and sending are separate tools: ``email``/``slack`` only read
(ungated, MCPMessagingTool), ``email_send``/``slack_post`` only send
(GatedMCPTool, listed in GATED_TOOLS). A send tool runs only with an
approval token that an ApprovalTokenVerifier accepts for that exact
payload, so reaching its execute() through an ordinary tool call can
never send anything.
"""

from __future__ import annotations

from typing import Protocol

from adapters.clients.mcp.registry import MCPServerRegistry
from adapters.observability.logger import get_logger
from core.exceptions.mcp import MCPError

log = get_logger(__name__)


class ApprovalTokenVerifier(Protocol):
    """
    What a gated tool needs from the approval system: whether an
    approval token covers this exact action + payload.
    """

    async def is_approved(
        self,
        *,
        token: str,
        action: str,
        payload: dict[str, object],
    ) -> bool: ...


class DenyAllApprovalVerifier:
    """
    Fail-closed ApprovalTokenVerifier: every gated action is denied.

    For tests and for wiring without a database. The application uses
    ApprovalRecordVerifier (application/authorization/approval_lifecycle/
    verifier.py), which checks the token against the Approval row.
    """

    async def is_approved(
        self,
        *,
        token: str,
        action: str,
        payload: dict[str, object],
    ) -> bool:
        return False


class MCPMessagingTool:
    """
    Mixin for tools backed by a messaging MCP server (Gmail, Slack).

    Not itself a Tool subclass -- mix in alongside Tool:

        class EmailTool(Tool, MCPMessagingTool):
            ...
    """

    def __init__(
        self,
        *,
        mcp_registry: MCPServerRegistry,
    ) -> None:
        self._mcp_registry = mcp_registry

    async def _call_mcp(
        self,
        *,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
        failure_message: str,
    ) -> str:
        """
        Call an MCP tool with consistent logging and error handling.
        Used for both ungated reads and (post-approval) gated sends.
        """

        try:
            result = await self._mcp_registry.call_tool(
                server_name=server_name,
                tool_name=tool_name,
                arguments=arguments,
            )

        except MCPError:
            log.exception("MCP call failed: server=%s tool=%s.", server_name, tool_name)
            raise

        if result.is_error:
            log.warning(
                "MCP call returned an error result: server=%s tool=%s.",
                server_name,
                tool_name,
            )
            return failure_message

        return result.as_text()


class GatedMCPTool(MCPMessagingTool):
    """
    Mixin for a side-effecting messaging tool: it runs only once
    _ensure_approved() accepts its approval token for the exact payload
    it is about to send. List the tool's name in GATED_TOOLS so an agent's
    call to it pauses for human approval instead of executing.
    """

    def __init__(
        self,
        *,
        mcp_registry: MCPServerRegistry,
        approval_service: ApprovalTokenVerifier,
    ) -> None:
        super().__init__(mcp_registry=mcp_registry)
        self._approval_service = approval_service

    async def _ensure_approved(
        self,
        *,
        approval_token: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        """
        Raises PermissionError if the token does not cover this exact
        action + payload. This is the gate — callers must not reach
        the MCP send/post call unless this passes.
        """

        approved = await self._approval_service.is_approved(
            token=approval_token,
            action=action,
            payload=payload,
        )

        if not approved:
            log.warning(
                "Approval denied or missing for action=%s payload_keys=%s.",
                action,
                list(payload.keys()),
            )
            raise PermissionError(f"'{action}' is not approved for this payload.")
