"""
Tool domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.enums import RetrievalSourceEnum


@dataclass(slots=True, frozen=True)
class ToolMetadataDTO:
    """
    Immutable metadata describing a tool.
    """

    name: str

    description: str


@dataclass(slots=True, frozen=True)
class ToolFileDTO:
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
class ToolRequestDTO:
    """
    Request passed to a tool.
    """

    query: str

    parameters: dict[str, Any] = field(
        default_factory=dict,
    )

    uploaded_files: tuple[
        ToolFileDTO,
        ...,
    ] = ()


@dataclass(slots=True, frozen=True)
class ToolResponseDTO:
    """
    Response returned by a tool.
    """

    content: tuple[
        RetrievedContentDTO,
        ...,
    ] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class RetrievedContentDTO:
    """
    Content retrieved from a knowledge source.
    """

    source: RetrievalSourceEnum
    source_name: str

    content: str

    score: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
