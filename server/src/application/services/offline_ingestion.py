"""
Offline document ingestion service.

Concrete implementation of the generic document-ingestion capability.

This implementation interprets `DocumentSource.location` as a local
filesystem path and delegates parsing and chunking to the ingestion
pipeline.

Flow:

    DocumentSource
        ↓
    local Path
        ↓
    FileParser
        ↓
    IngestionPipeline
        ↓
    Iterator[IngestionChunk]

This service does not perform parsing, sanitization, validation,
chunking, embedding, indexing, or persistence itself.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from adapters.observability.logger import get_logger
from rag.ingestion.exceptions import IngestionError
from rag.ingestion.models import DocumentSource, IngestionChunk
from rag.ingestion.parsers.file import FileParser
from rag.ingestion.pipeline import IngestionPipeline

logger = get_logger(__name__)


class OfflineIngestionService:
    """
    Local filesystem implementation of document ingestion.

    The service implements DocumentIngestionProtocol structurally.

    Only this concrete implementation knows that `location` represents
    a local filesystem path.

    One instance can safely be reused for multiple documents.
    """

    def __init__(
        self,
        *,
        parser: FileParser | None = None,
        pipeline: IngestionPipeline[Path] | None = None,
    ) -> None:
        if pipeline is not None:
            self._pipeline = pipeline
            return

        self._parser = parser or FileParser()

        self._pipeline = IngestionPipeline(
            parser=self._parser,
        )

    def ingest(
        self,
        *,
        source: DocumentSource,
    ) -> Iterator[IngestionChunk]:
        """
        Lazily ingest one local document.

        `DocumentSource.location` is interpreted as a filesystem path.

        No complete document or chunk collection is accumulated.

        Args:
            source:
                Document source descriptor.

        Yields:
            IngestionChunk objects.

        Raises:
            IngestionError:
                If the source cannot be ingested.
        """

        if not isinstance(source, DocumentSource):
            raise TypeError(
                "source must be a DocumentSource.",
            )

        if not source.location.strip():
            raise ValueError(
                "source.location must not be empty.",
            )

        path = Path(source.location)

        if not path.is_file():
            raise IngestionError(
                f"Source document does not exist: {path}",
            )

        logger.info(
            "Starting offline document ingestion.",
            extra={
                "source": str(path),
                "source_id": source.id,
            },
        )

        chunk_count = 0

        try:
            for chunk in self._pipeline.ingest(
                source=path,
            ):
                chunk_count += 1
                yield chunk

        except IngestionError:
            logger.exception(
                "Offline document ingestion failed.",
                extra={
                    "source": str(path),
                    "source_id": source.id,
                    "chunks_produced": chunk_count,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error during offline document ingestion.",
                extra={
                    "source": str(path),
                    "source_id": source.id,
                    "chunks_produced": chunk_count,
                },
            )

            raise IngestionError(
                f"Failed to ingest document: {path}",
            ) from exc

        else:
            logger.info(
                "Completed offline document ingestion.",
                extra={
                    "source": str(path),
                    "source_id": source.id,
                    "chunks_produced": chunk_count,
                },
            )
