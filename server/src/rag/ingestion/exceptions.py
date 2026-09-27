from __future__ import annotations

from core.exceptions.base import AppError


class IngestionError(AppError):
    """Base exception for document ingestion failures."""


class FileReadError(IngestionError):
    """Raised when a local file cannot be read or opened."""


class FileDecodeError(FileReadError):
    """Raised when a text file cannot be decoded."""


class FileSourceError(FileReadError):
    """Raised when the file source is invalid."""


class SanitizationError(IngestionError):
    """Raised when document sanitization fails."""


class ContentValidationError(IngestionError):
    """Raised when document content validation fails."""


class ChunkingError(IngestionError):
    """Raised when document content chunk fails."""
