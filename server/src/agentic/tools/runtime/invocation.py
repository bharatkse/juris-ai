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
    Parameter validation (the tool's params_model)
        ↓
    Tool execution
        ↓
    ToolResult

Parameters come from the model, so they are untrusted: they are validated
and bounded before the tool runs, and a failure is reported to the model
as a short message naming only fields and constraints -- never the raw
exception text or the rejected values, which could carry injected text
back into the next prompt. The full exception is logged instead.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from adapters.observability.logger import get_logger
from agentic.registry.protocols import ToolRegistryProtocol
from agentic.tools.result import ToolEvidence, ToolResult

logger = get_logger(__name__)

# A parameter name is echoed back to the model only if it looks like an
# identifier; anything else is model-supplied text and is not repeated.
_PARAMETER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

_BOUND_MESSAGES = {
    "less_than_equal": ("le", "must be <= {}"),
    "less_than": ("lt", "must be < {}"),
    "greater_than_equal": ("ge", "must be >= {}"),
    "greater_than": ("gt", "must be > {}"),
    "string_too_short": ("min_length", "must be at least {} characters"),
    "string_too_long": ("max_length", "must be at most {} characters"),
}


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

        if tool.params_model is None:
            logger.warning(
                "Refused a call to a tool agents can't call: tool=%s.",
                tool_name,
            )

            return self._failed(
                tool_name=tool_name,
                error=f"Tool '{tool_name}' can't be called by an agent.",
                error_type="ToolNotCallable",
            )

        try:
            params = tool.params_model.model_validate(parameters or {})

        except ValidationError as exc:
            logger.info(
                "Rejected tool parameters: tool=%s errors=%s.",
                tool_name,
                [(error["type"], error["loc"]) for error in exc.errors(include_input=False)],
            )

            return self._failed(
                tool_name=tool_name,
                error=_describe_invalid_parameters(tool_name=tool_name, error=exc),
                error_type="InvalidParameters",
            )

        try:
            # exclude_unset: the tool's own execute() defaults apply to
            # anything the model didn't pass.
            content = await tool.execute(
                **params.model_dump(exclude_unset=True),
            )

        except Exception as exc:
            logger.exception(
                "Tool execution failed: tool=%s.",
                tool_name,
            )

            return self._failed(
                tool_name=tool_name,
                error=f"Tool '{tool_name}' failed while running.",
                error_type=type(exc).__name__,
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

    @staticmethod
    def _failed(
        *,
        tool_name: str,
        error: str,
        error_type: str,
    ) -> ToolResult:
        return ToolResult(
            tool_name=tool_name,
            success=False,
            content="",
            evidence=(),
            execution_metadata={
                "error_type": error_type,
            },
            error=error,
        )


def _describe_invalid_parameters(*, tool_name: str, error: ValidationError) -> str:
    """
    One short, model-readable sentence per problem: the field and the
    constraint it broke. Never includes the rejected value, and repeats a
    parameter name only if it looks like an identifier.
    """

    problems: list[str] = []

    for item in error.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in item["loc"])
        field = location if _PARAMETER_NAME.match(location) else "a parameter"
        error_type = item["type"]
        context = item.get("ctx") or {}

        if error_type == "extra_forbidden":
            problems.append(
                f"'{field}' is not a parameter of this tool"
                if field != "a parameter"
                else "an unknown parameter was passed"
            )
        elif error_type == "missing":
            problems.append(f"'{field}' is required")
        elif error_type == "literal_error":
            problems.append(
                f"'{field}' must be one of {context.get('expected', 'the allowed values')}"
            )
        elif error_type in _BOUND_MESSAGES:
            key, template = _BOUND_MESSAGES[error_type]
            problems.append(f"'{field}' " + template.format(context.get(key, "the allowed limit")))
        elif error_type.endswith(("_type", "_parsing")):
            problems.append(f"'{field}' has the wrong type")
        else:
            problems.append(f"'{field}' is invalid")

    return f"Invalid parameters for tool '{tool_name}': " + "; ".join(problems) + "."
