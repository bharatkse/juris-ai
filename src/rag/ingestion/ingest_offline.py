"""
Offline RAG indexing entry point.

Discovers supported legal source files and delegates each document to
DocumentIndexingService.

Flow:

    Source Directory
        ↓
    DocumentSource
        ↓
    DocumentIndexingService
        ↓
    DocumentIngestionProtocol
        ↓
    ChunkMapper
        ↓
    RAGIndexer
        ↓
    EmbeddingProvider
        ↓
    VectorStore
        ↓
    RAGIndexPersistenceService
        ↓
    ┌──────────────────────────────┐
    ↓                              ↓
DocumentChunk            DocumentChunkEmbedding
    ↓                              ↓
PostgreSQL FTS/BM25              pgvector

This module is the offline CLI composition root.

It is responsible for:

    - CLI argument parsing
    - source-file discovery
    - DocumentSource construction
    - concrete dependency wiring
    - corpus-level iteration
    - per-document success/failure handling

It does not:
    - parse documents
    - sanitize content
    - validate content
    - chunk documents
    - map ingestion chunks
    - generate embeddings
    - persist chunks directly
    - perform retrieval
    - perform reranking
    - call an LLM
    - manage database transactions
    - manage Celery
    - use multiprocessing
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Iterator
from pathlib import Path

from adapters.observability.logger import get_logger
from application.services.document_indexing import (
    DocumentIndexingService,
)
from core.exceptions.rag import RAGError
from rag.embeddings import (
    SentenceTransformerEmbeddingProvider,
)
from rag.indexer import RAGIndexer
from rag.ingestion.exceptions import IngestionError
from rag.ingestion.models import DocumentSource
from rag.models import IndexedRepresentation
from rag.pgvector_store import PgVectorStore

logger = get_logger(__name__)


_SUPPORTED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".docx",
        ".txt",
        ".md",
        ".html",
        ".htm",
    }
)


def discover_files(
    *,
    source_dir: Path,
) -> Iterator[Path]:
    """
    Lazily discover supported legal source files recursively.

    Files are yielded one at a time.

    No complete file list is materialized in memory.

    Args:
        source_dir:
            Root directory containing legal source documents.

    Yields:
        Supported source-file paths.

    Raises:
        ValueError:
            If the source directory does not exist or is not a directory.

        IngestionError:
            If filesystem discovery fails.
    """

    if not source_dir.exists():
        raise ValueError(
            f"Source directory does not exist: {source_dir}",
        )

    if not source_dir.is_dir():
        raise ValueError(
            f"Source path is not a directory: {source_dir}",
        )

    try:
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                continue

            yield path

    except OSError as exc:
        logger.exception(
            "Failed to discover offline source files.",
            extra={
                "source_dir": str(source_dir),
            },
        )

        raise IngestionError(
            "Failed to discover offline source files.",
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description="Index legal source documents for offline RAG.",
    )

    parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory containing legal source documents.",
    )

    return parser


def _build_source(
    *,
    path: Path,
) -> DocumentSource:
    """
    Build a DocumentSource for a local filesystem document.

    The CLI is responsible only for translating the discovered
    filesystem path into the generic document-source descriptor.

    Args:
        path:
            Discovered local source-file path.

    Returns:
        Generic document source descriptor.
    """

    resolved_path = path.resolve()

    return DocumentSource(
        id=None,
        location=str(resolved_path),
    )


def _build_indexing_service() -> DocumentIndexingService:
    """
    Build the concrete document-indexing dependency graph.

    This function is the CLI composition root.

    Dependency graph:

        SentenceTransformerEmbeddingProvider
                    ↓
                RAGIndexer
                    ↓
                PgVectorStore
                    ↓
        RAGIndexPersistenceService

        OfflineIngestionService
                    ↓
        DocumentIndexingService
                    ↓
                RAGIndexer

    Keyword/BM25 retrieval is intentionally not wired here.

    PostgreSQL full-text/BM25 search operates over the persisted
    DocumentChunk representation and is exposed separately through
    PostgresKeywordStore.

    Returns:
        Fully configured DocumentIndexingService.
    """

    from application.services.offline_ingestion import (
        OfflineIngestionService,
    )

    embedding_provider = SentenceTransformerEmbeddingProvider()

    vector_store = PgVectorStore()

    indexer = RAGIndexer(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    ingestion_service = OfflineIngestionService()

    return DocumentIndexingService(
        ingestion_service=ingestion_service,
        indexer=indexer,
    )


async def _run(
    *,
    source_dir: Path,
) -> int:
    """
    Execute the asynchronous offline RAG indexing workflow.

    This function owns corpus-level iteration and delegates each
    document to DocumentIndexingService.

    Args:
        source_dir:
            Root directory containing legal source documents.

    Returns:
        Zero when all discovered documents succeed.
        One when one or more documents fail.
    """

    indexing_service = _build_indexing_service()

    processed_files = 0
    failed_files = 0
    total_chunks = 0

    for path in discover_files(
        source_dir=source_dir,
    ):
        source = _build_source(
            path=path,
        )

        logger.info(
            "Processing offline source.",
            extra={
                "source": source.location,
                "source_id": source.id,
            },
        )

        try:
            result: IndexedRepresentation = await indexing_service.index(
                source=source,
            )

            processed_files += 1
            total_chunks += result.chunk_count

            logger.info(
                "Offline source indexed.",
                extra={
                    "source": source.location,
                    "source_id": source.id,
                    "chunk_count": result.chunk_count,
                    "embedding_model": result.embedding_model,
                    "embedding_dimension": result.embedding_dimension,
                },
            )

        except IngestionError:
            failed_files += 1

            logger.exception(
                "Offline source ingestion failed.",
                extra={
                    "source": source.location,
                    "source_id": source.id,
                },
            )

        except RAGError:
            failed_files += 1

            logger.exception(
                "Offline source RAG indexing failed.",
                extra={
                    "source": source.location,
                    "source_id": source.id,
                },
            )

        except Exception:
            failed_files += 1

            logger.exception(
                "Unexpected failure while indexing offline source.",
                extra={
                    "source": source.location,
                    "source_id": source.id,
                },
            )

    logger.info(
        "Offline RAG indexing completed.",
        extra={
            "processed_files": processed_files,
            "failed_files": failed_files,
            "chunks_indexed": total_chunks,
        },
    )

    return 1 if failed_files else 0


def main() -> int:
    """
    Execute offline document indexing.

    The CLI entry point remains synchronous and owns the asyncio
    event-loop boundary.

    Concrete dependencies are constructed by the composition root
    inside the asynchronous workflow.

    Returns:
        Zero when all discovered documents succeed.
        One when one or more documents fail.
        130 when interrupted by the user.
    """

    parser = _build_parser()
    args = parser.parse_args()

    try:
        return asyncio.run(
            _run(
                source_dir=args.source_dir,
            ),
        )

    except (ValueError, IngestionError, RAGError) as exc:
        logger.error(
            "Offline RAG indexing could not start: %s",
            exc,
        )

        return 1

    except KeyboardInterrupt:
        logger.warning(
            "Offline RAG indexing interrupted by user.",
        )

        return 130

    except Exception:
        logger.exception(
            "Unexpected failure during offline RAG indexing.",
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
