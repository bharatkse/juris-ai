from __future__ import annotations

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

    def to_dict(self) -> dict[str, Any]:
        """
        Plain, JSON-safe representation.

        Needed anywhere a ToolResult has to cross a boundary that only
        reliably round-trips JSON-primitive types -- LangGraph's
        interrupt()/Command(resume=...) payloads (agents/runtime/
        continuation.py's gated-tool pause/resume) and, for the same
        reason, its @task checkpointing (this dataclass itself isn't a
        registered msgpack type, so passing it through directly hits a
        pickle fallback LangGraph warns is being phased out).
        """

        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "content": self.content,
            "evidence": [
                {
                    "content": item.content,
                    "score": item.score,
                    "source": item.source,
                    "metadata": item.metadata,
                }
                for item in self.evidence
            ],
            "execution_metadata": self.execution_metadata,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolResult:
        """Reconstruct from to_dict()'s output."""

        return cls(
            tool_name=data["tool_name"],
            success=data["success"],
            content=data["content"],
            evidence=tuple(
                ToolEvidence(
                    content=item["content"],
                    score=item.get("score"),
                    source=item.get("source"),
                    metadata=item.get("metadata", {}),
                )
                for item in data.get("evidence", ())
            ),
            execution_metadata=data.get("execution_metadata", {}),
            error=data.get("error"),
        )
