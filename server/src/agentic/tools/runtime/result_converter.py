"""
Conversion between tool execution results and agent reasoning context.
"""

from __future__ import annotations

from agentic.tools.result import ToolResult
from core.dto.tool import RetrievedContentDTO
from core.enums import RetrievalSourceEnum


class ToolResultConverter:
    """
    Convert ToolResult objects into bounded agent reasoning context.

    Tool execution is deliberately kept separate from reasoning.
    This converter only translates the tool result into the existing
    RetrievedContentDTO contract consumed by AgentExecutionHandle.
    """

    _DEFAULT_SOURCE = RetrievalSourceEnum.MEMORY

    @classmethod
    def to_reasoning_context(
        cls,
        *,
        result: ToolResult,
    ) -> tuple[RetrievedContentDTO, ...]:
        """
        Convert a ToolResult into reasoning-context entries.

        Explicit ToolEvidence entries are preferred. If a tool returns
        only its top-level content, that content is retained as one
        context item.

        A tool is not itself a RetrievalSourceEnum value, so an unknown
        source is represented as MEMORY rather than inventing a new
        enum member.
        """

        if result.evidence:
            return tuple(
                cls._to_retrieved_content(
                    result=result,
                    content=evidence.content,
                    score=evidence.score,
                    source=evidence.source,
                    metadata=evidence.metadata,
                )
                for evidence in result.evidence
                if evidence.content
            )

        if not result.content:
            return ()

        return (
            cls._to_retrieved_content(
                result=result,
                content=result.content,
                score=None,
                source=None,
                metadata={},
            ),
        )

    @classmethod
    def _to_retrieved_content(
        cls,
        *,
        result: ToolResult,
        content: str,
        score: float | None,
        source: str | None,
        metadata: dict,
    ) -> RetrievedContentDTO:
        return RetrievedContentDTO(
            source=cls._resolve_source(source),
            source_name=result.tool_name,
            content=content,
            score=score,
            metadata={
                **metadata,
                "tool_name": result.tool_name,
                "tool_success": result.success,
                **result.execution_metadata,
            },
        )

    @classmethod
    def _resolve_source(
        cls,
        source: str | None,
    ) -> RetrievalSourceEnum:
        if not source:
            return cls._DEFAULT_SOURCE

        try:
            return RetrievalSourceEnum(source)
        except ValueError:
            return cls._DEFAULT_SOURCE
