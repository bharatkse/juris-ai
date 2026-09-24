"""
Tool execution service.

This module contains the runtime service responsible for executing
agent-callable tools.

ToolExecutionService is intentionally independent of:
    - LangGraph
    - agent lifecycle state
    - agent policy
    - authorization
    - HITL approval
    - planning
    - agent delegation

Its responsibility is limited to:

    Agent action
        ↓
    Tool resolution
        ↓
    Tool execution
        ↓
    ToolResult
"""

from __future__ import annotations

from typing import Any

from agentic.registry.protocols import ToolRegistryProtocol
from agentic.tools.result import ToolEvidence, ToolResult


class ToolExecutionService:
    """
    Executes an agent-callable tool resolved from ToolRegistry.

    This service is stateless and safe to reuse across concurrent
    executions.

    Responsibilities:
        - resolve a tool from ToolRegistry
        - invoke Tool.execute()
        - convert execution outcomes into ToolResult

    This service does not:
        - evaluate agent policy
        - perform user/tenant authorization
        - evaluate HITL approval
        - execute agents
        - perform planning
        - manage agent lifecycle state
        - mutate LangGraph state
        - retain request-scoped state
    """

    # Generic source classification by tool name -- this service does
    # not otherwise know anything tool-specific, and this mapping is
    # deliberately narrow (retrieval-shaped tools only) rather than a
    # step toward per-tool business logic living here.
    _SOURCE_BY_TOOL: dict[str, str] = {
        "retriever": "document",
    }

    def __init__(
        self,
        *,
        tool_registry: ToolRegistryProtocol,
    ) -> None:
        self._tool_registry = tool_registry

    async def execute(
        self,
        *,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> ToolResult:
        """
        Resolve and execute one tool invocation.

        Tool resolution failures are intentionally allowed to propagate
        because they indicate that the requested tool is unavailable
        or incorrectly configured.

        Tool execution failures are converted into a failed ToolResult
        so callers can continue handling the result through the normal
        tool-execution boundary.
        """

        tool = self._tool_registry.resolve(
            key=tool_name,
        )

        try:
            content = await tool.execute(
                **parameters,
            )

        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                content="",
                evidence=(),
                execution_metadata={
                    "error_type": type(exc).__name__,
                },
                error=str(exc),
            )

        return ToolResult(
            tool_name=tool_name,
            success=True,
            content=content,
            evidence=(
                ToolEvidence(
                    content=content,
                    source=self._SOURCE_BY_TOOL.get(tool_name),
                ),
            ),
            execution_metadata={},
            error=None,
        )
