from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolEvidence:
    """
    Evidence produced by a tool.

    Score is optional because not every tool produces a relevance score.
    """

    content: str
    score: float | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(frozen=True, slots=True)
class ToolResult:
    """
    Result produced by a tool execution.
    """

    tool_name: str
    success: bool

    content: str

    evidence: tuple[ToolEvidence, ...] = ()

    execution_metadata: dict[str, Any] = field(default_factory=dict)

    error: str | None = None
