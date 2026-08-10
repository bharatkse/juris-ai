"""
Tool domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.enums import RetrievalSource


@dataclass(slots=True, frozen=True)
class ToolMetadata:
    """
    Immutable metadata describing a tool.
    """

    name: str

    description: str


@dataclass(slots=True, frozen=True)
class ToolFile:
    """
    File available to a tool.
    """

    filename: str

    content: bytes

    content_type: str

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class ToolRequest:
    """
    Request passed to a tool.
    """

    query: str

    parameters: dict[str, Any] = field(
        default_factory=dict,
    )

    uploaded_files: tuple[
        ToolFile,
        ...,
    ] = ()


@dataclass(slots=True, frozen=True)
class ToolResponse:
    """
    Response returned by a tool.
    """

    content: tuple[
        RetrievedContent,
        ...,
    ] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class RetrievedContent:
    """
    Content retrieved from a knowledge source.
    """

    source: RetrievalSource

    content: str

    score: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
