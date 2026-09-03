"""
RAG index persistence application service.

Coordinates persistence of RAG chunks and their embedding
representations.

Flow:

    RAG Chunk + Embedding
        ↓
    RAGIndexPersistenceService
        ↓
    ┌──────────────────────────────┬──────────────────────────────┐
    ↓                              ↓
KnowledgeChunkRepository    KnowledgeEmbeddingRepository
    ↓                              ↓
KnowledgeChunk              KnowledgeEmbedding

This service owns the application-level persistence orchestration
and transaction boundary.

It does NOT:
    - parse documents
    - ingest documents
    - sanitize content
    - chunk text
    - generate embeddings
    - perform retrieval
    - perform reranking
    - call an LLM
    - contain SQL queries
    - construct SQLAlchemy queries
"""

from __future__ import annotations

import hashlib

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.knowledge_chunk import (
    KnowledgeChunkRepository,
)
from adapters.persistence.sqlalchemy.repositories.knowledge_embedding import (
    KnowledgeEmbeddingRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from core.exceptions.rag import RAGError
from rag.models import Chunk
from rag.protocols.index_persistence import RAGIndexPersistenceProtocol

logger = get_logger(__name__)


class RAGIndexPersistenceService(RAGIndexPersistenceProtocol):
    """
    Application service coordinating persistence of RAG index data.

    Textual chunks and their embeddings are persisted within the same
    database transaction.

    The service does not contain SQLAlchemy queries. Persistence
    details remain inside repository implementations.
    """

    def __init__(self) -> None:
        """Initialize the RAG index persistence service."""

        self._session_factory = session_factory

    async def persist(
        self,
        *,
        chunks: list[Chunk],
        vectors: list[list[float]],
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        """
        Persist a bounded batch of RAG chunks and embeddings.

        The vectors must correspond to the chunks in the same order.

        Both chunks and embeddings are persisted within one transaction.

        Args:
            chunks:
                RAG-domain chunks to persist.

            vectors:
                Embedding vectors corresponding to ``chunks``.

            embedding_model:
                Model used to generate the vectors.

            embedding_dimension:
                Expected dimension of every vector.

        Raises:
            RAGError:
                If validation or persistence fails.
        """

        if not chunks:
            return

        self._validate_input(
            chunks=chunks,
            vectors=vectors,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
        )

        try:
            async with self._session_factory() as session:
                chunk_repository = KnowledgeChunkRepository(
                    session=session,
                )

                embedding_repository = KnowledgeEmbeddingRepository(
                    session=session,
                )

                for chunk, vector in zip(
                    chunks,
                    vectors,
                    strict=True,
                ):
                    persisted_chunk = await chunk_repository.get_by_id(
                        chunk_id=chunk.id,
                    )

                    chunk_metadata = {
                        **chunk.metadata,
                        "source_id": chunk.source_id,
                    }

                    if persisted_chunk is None:
                        await chunk_repository.create(
                            chunk_id=chunk.id,
                            document_id=None,
                            text=chunk.text,
                            chunk_metadata=chunk_metadata,
                        )
                    else:
                        await chunk_repository.update(
                            chunk=persisted_chunk,
                            text=chunk.text,
                            chunk_metadata=chunk_metadata,
                        )

                    await embedding_repository.upsert(
                        chunk_id=chunk.id,
                        embedding_model=embedding_model,
                        vector=vector,
                    )

                await session.commit()

        except RAGError:
            logger.exception(
                "RAG index persistence failed.",
                extra={
                    "chunk_count": len(chunks),
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected RAG index persistence failure.",
                extra={
                    "chunk_count": len(chunks),
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                },
            )

            raise RAGError(
                message="Failed to persist RAG index representations.",
            ) from exc

        logger.debug(
            "RAG index persistence completed.",
            extra={
                "chunk_count": len(chunks),
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
            },
        )

    @staticmethod
    def _validate_input(
        *,
        chunks: list[Chunk],
        vectors: list[list[float]],
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        """Validate persistence input before opening a database transaction."""

        if len(chunks) != len(vectors):
            raise RAGError(
                message=(
                    "Vector count does not match chunk count: "
                    f"chunks={len(chunks)}, vectors={len(vectors)}."
                ),
            )

        if not embedding_model.strip():
            raise RAGError(
                message="Embedding model must not be empty.",
            )

        if embedding_dimension <= 0:
            raise RAGError(
                message="Embedding dimension must be greater than zero.",
            )

        for index, vector in enumerate(vectors):
            if len(vector) != embedding_dimension:
                raise RAGError(
                    message=(
                        "Embedding dimension mismatch at index "
                        f"{index}: expected {embedding_dimension}, "
                        f"received {len(vector)}."
                    ),
                )

    @staticmethod
    def _document_id(source_id: str | None) -> str | None:
        """
        Return a deterministic document ID for a source identity.

        This helper is retained for callers that need deterministic
        parent-document identity. It does not imply that a document
        record must exist for every persisted chunk.
        """

        if not source_id:
            return None

        if source_id.startswith("ksrc_") and len(source_id) <= 64:
            return source_id

        digest = hashlib.sha256(
            source_id.encode("utf-8"),
        ).hexdigest()

        return f"ksrc_{digest[:59]}"
