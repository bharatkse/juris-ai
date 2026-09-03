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
DocumentChunkRepository    DocumentChunkEmbeddingRepository
    ↓                              ↓
DocumentChunk              DocumentChunkEmbedding

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

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.document_chunk import (
    DocumentChunkRepository,
)
from adapters.persistence.sqlalchemy.repositories.document_chunk_embedding import (
    DocumentChunkEmbeddingRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from core.exceptions.rag import RAGError
from rag.models import Chunk
from rag.protocols.index_persistence import RAGIndexPersistenceProtocol

logger = get_logger(__name__)


class RAGIndexPersistenceService(RAGIndexPersistenceProtocol):
    """
    Application service coordinating persistence of RAG index data.

    The service coordinates textual chunk persistence and embedding
    persistence within a single transaction.

    Repository implementations remain responsible only for their
    individual persistence operations.
    """

    def __init__(self) -> None:
        """
        Initialize the RAG index persistence service.

        The service uses the shared SQLAlchemy session factory.
        """

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

        Both textual chunks and embedding representations are persisted
        within the same database transaction.

        Args:
            chunks:
                RAG-domain chunks to persist.

            vectors:
                Embedding vectors corresponding to the chunks.

            embedding_model:
                Model used to generate the vectors.

            embedding_dimension:
                Expected vector dimension.

        Raises:
            RAGError:
                If validation or persistence fails.
        """

        if not chunks:
            return

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

        try:
            async with self._session_factory() as session:
                chunk_repository = DocumentChunkRepository(
                    session=session,
                )

                embedding_repository = DocumentChunkEmbeddingRepository(
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

                    if persisted_chunk is None:
                        await chunk_repository.create(
                            chunk_id=chunk.id,
                            document_id=None,
                            text=chunk.text,
                            chunk_metadata={
                                **chunk.metadata,
                                "source_id": chunk.source_id,
                            },
                        )
                    else:
                        await chunk_repository.update(
                            chunk=persisted_chunk,
                            text=chunk.text,
                            chunk_metadata=chunk.metadata,
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
