"""
Shared base for gated messaging tools.

EmailTool and SlackTool were near-identical: same approval-check
logic, same MCP-call-with-error-handling wrapper, same
read-is-ungated/write-is-gated split. Extracted the common parts here
so each tool file only contains what's actually specific to it.
"""

from __future__ import annotations

from adapters.clients.mcp.registry import MCPServerRegistry
from adapters.observability.logger import get_logger
from application.authorization.approval_lifecycle.protocols import (
    ApprovalLifecycleServiceProtocol,
)
from core.exceptions.mcp import MCPError

log = get_logger(__name__)


class GatedMCPTool:
    """
    Mixin providing the dry-run -> approval -> execute triplet for
    tools backed by a side-effecting MCP server (Gmail, Slack, and
    any future messaging/write-capable integration).

    Not itself a Tool subclass — mix in alongside Tool:

        class EmailTool(Tool, GatedMCPTool):
            ...
    """

    def __init__(
        self,
        *,
        mcp_registry: MCPServerRegistry,
        approval_service: ApprovalLifecycleServiceProtocol,
    ) -> None:
        self._mcp_registry = mcp_registry
        self._approval_service = approval_service

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
        Used for both ungated reads and (post-approval) gated writes.
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
