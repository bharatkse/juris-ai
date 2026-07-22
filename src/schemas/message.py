"""
Pydantic schemas for document-related HTTP endpoints.
These are the shapes the API accepts and returns — kept separate from
the domain models in app/models/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.core.enums import DocumentStatus


class DocumentUploadResponse(BaseModel):
    """Returned immediately after a successful file upload & ingestion."""

    document_id: str
    filename: str
    file_size: int
    status: DocumentStatus
    message: str


class DocumentOut(BaseModel):
    """Full document details returned by GET /documents/{id}."""

    id: str
    filename: str
    original_name: str
    file_size: int
    file_size_mb: float
    status: DocumentStatus
    chunk_count: int
    page_count: int
    doc_type: str
    error_message: str | None
    doc_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, doc) -> DocumentOut:
        """Build from a DocumentORM instance."""
        return cls(
            id=doc.id,
            filename=doc.filename,
            original_name=doc.original_name,
            file_size=doc.file_size,
            file_size_mb=round(doc.file_size / (1024 * 1024), 2),
            status=doc.status,
            chunk_count=doc.chunk_count,
            page_count=doc.page_count,
            doc_type=doc.doc_metadata.get("doc_type", "unknown"),
            error_message=doc.error_message,
            doc_metadata=doc.doc_metadata,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            indexed_at=doc.indexed_at,
        )


class DocumentSummary(BaseModel):
    """Lightweight summary used in list responses."""

    id: str
    filename: str
    status: DocumentStatus
    chunk_count: int
    page_count: int
    file_size_mb: float
    doc_type: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, doc) -> DocumentSummary:
        return cls(
            id=doc.id,
            filename=doc.filename,
            status=doc.status,
            chunk_count=doc.chunk_count,
            page_count=doc.page_count,
            file_size_mb=round(doc.file_size / (1024 * 1024), 2),
            doc_type=doc.doc_metadata.get("doc_type", "unknown"),
            created_at=doc.created_at,
        )


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    items: list[DocumentSummary]
    total: int
    skip: int
    limit: int


class DocumentDeleteResponse(BaseModel):
    """Confirmation of document deletion."""

    document_id: str
    message: str
    success: bool = True
