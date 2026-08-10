"""
Provider-independent storage models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True, frozen=True)
class UploadRequestDTO:
    """
    Upload request.

    object_id identifies the logical storage container.

    Examples:
        Local Storage: conversation_id
        S3: object prefix
        Azure Blob: blob prefix
    """

    object_id: str

    filename: str

    content: bytes

    content_type: str

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class UploadResponseDTO:
    """
    Upload response.
    """

    object: StoredObjectDTO


@dataclass(slots=True, frozen=True)
class DownloadRequestDTO:
    """
    Download request.
    """

    object_id: str

    filename: str


@dataclass(slots=True, frozen=True)
class DownloadResponseDTO:
    """
    Download response.
    """

    object: StoredObjectDTO

    content: bytes


@dataclass(slots=True, frozen=True)
class DeleteRequestDTO:
    """
    Delete request.
    """

    object_id: str

    filename: str


@dataclass(slots=True, frozen=True)
class ExistsRequestDTO:
    """
    Exists request.
    """

    object_id: str

    filename: str


@dataclass(slots=True, frozen=True)
class MetadataRequestDTO:
    """
    Metadata request.
    """

    object_id: str

    filename: str


@dataclass(slots=True, frozen=True)
class ListRequestDTO:
    """
    List request.
    """

    object_id: str

    prefix: str | None = None

    limit: int | None = None


@dataclass(slots=True, frozen=True)
class StoredObjectDTO:
    """
    Stored object metadata.

    object_id identifies the logical storage container.
    filename identifies the stored object within that container.
    """

    object_id: str

    filename: str

    content_type: str

    size: int

    checksum: str | None = None

    storage_path: str | None = None

    created_at: datetime = field(
        default_factory=lambda: datetime.now(
            UTC,
        ),
    )

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True, frozen=True)
class ListResponseDTO:
    """
    List response.
    """

    objects: tuple[
        StoredObjectDTO,
        ...,
    ]
