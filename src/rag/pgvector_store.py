"""
PostgreSQL/pgvector vector-store adapter.

Infrastructure adapter between the RAG vector-store capability and the
PostgreSQL/pgvector implementation.

RAG domain models live in:
    rag.models

Capability contracts live in:
    rag.protocols

Application persistence orchestration lives in:
    application.services.rag_index_persistence

This adapter does NOT:
    - construct persistence entities
    - coordinate persistence repositories
    - manage transactions
    - access SQLAlchemy sessions directly
    - manage document lifecycle
    - extract document text
    - chunk documents
    - generate embeddings
    - perform reranking
    - call an LLM
"""

from __future__ import annotations

from typing import Any

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.rag_retrieval import RAGRetrievalRepository
from adapters.persistence.sqlalchemy.session import session_factory as default_session_factory
from application.services.rag_index_persistence import (
    RAGIndexPersistenceService,
)
from core.exceptions.rag import RAGError
from rag.models import (
    Chunk,
    EmbeddingRepresentation,
    RetrievalResult,
)
from rag.protocols.index_persistence import RAGIndexPersistenceProtocol
from rag.protocols.vector import VectorStoreProtocol

logger = get_logger(__name__)


class PgVectorStore(VectorStoreProtocol):
    """
    PostgreSQL/pgvector implementation of VectorStoreProtocol.

    Responsibilities:

        - delegate vector persistence to the RAG index persistence
          capability
        - delegate vector retrieval to the persistence retrieval
          repository
        - translate persistence entities into RAG-domain models

    This adapter does not own SQLAlchemy sessions or repositories.
    """

    def __init__(
        self,
        *,
        index_persistence_service: RAGIndexPersistenceProtocol | None = None,
        session_factory: Any | None = None,
    ) -> None:
        """
        Initialize the PostgreSQL/pgvector adapter.

        Args:
            index_persistence_service:
                Application capability responsible for coordinating
                chunk and embedding persistence.

            session_factory:
                Factory returning a configured SQLAlchemy session.

                The factory is injectable so this adapter does not own
                SQLAlchemy session construction.
        """

        self._index_persistence_service = index_persistence_service or RAGIndexPersistenceService()

        self._session_factory = session_factory or default_session_factory

    async def upsert(
        self,
        *,
        chunks: list[Chunk],
        vectors: list[list[float]],
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        """
        Persist vector representations through the indexing capability.

        This adapter does not coordinate persistence repositories or
        manage database transactions.
        """

        if not chunks:
            return

        if len(chunks) != len(vectors):
            raise RAGError(
                message=(
                    "Vector count does not match chunk count: "
                    f"chunks={len(chunks)}, "
                    f"vectors={len(vectors)}."
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
            await self._index_persistence_service.persist(
                chunks=chunks,
                vectors=vectors,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )

        except RAGError:
            logger.exception(
                "PGVector upsert failed.",
                extra={
                    "chunk_count": len(chunks),
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected PGVector upsert failure.",
                extra={
                    "chunk_count": len(chunks),
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                },
            )

            raise RAGError(
                message="Failed to persist RAG vector representations.",
            ) from exc

    async def query(
        self,
        *,
        vector: list[float],
        top_k: int,
        embedding_model: str,
        allowed_source_ids: set[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve chunks using pgvector similarity.

        PostgreSQL performs:

            - vector similarity
            - embedding-model filtering
            - source filtering
            - ranking
            - top-K limiting

        The repository returns:

            (
                DocumentChunkEmbedding,
                similarity_score,
            )

        The embedding entity exposes its associated DocumentChunk
        through the eagerly loaded `chunk` relationship.
        """

        if not vector:
            return []

        if top_k <= 0:
            return []

        if not embedding_model.strip():
            return []

        try:
            async with self._session_factory() as session:
                repository = RAGRetrievalRepository(
                    session=session,
                )

                rows = await repository.vector_search(
                    vector=vector,
                    embedding_model=embedding_model,
                    top_k=top_k,
                    source_ids=allowed_source_ids,
                    metadata_filters=metadata_filters,
                )

        except RAGError:
            logger.exception(
                "PGVector retrieval failed.",
                extra={
                    "top_k": top_k,
                    "embedding_model": embedding_model,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected PGVector retrieval failure.",
                extra={
                    "top_k": top_k,
                    "embedding_model": embedding_model,
                },
            )

            raise RAGError(
                message="Failed to retrieve RAG vector representations.",
            ) from exc

        try:
            results: list[RetrievalResult] = []

            for embedding, score in rows:
                chunk = embedding.chunk

                rag_chunk = Chunk(
                    id=chunk.id,
                    source_id=(chunk.chunk_metadata.get("source_id") or chunk.document_id),
                    text=chunk.text,
                    metadata=dict(
                        chunk.chunk_metadata or {},
                    ),
                )

                rag_embedding = EmbeddingRepresentation(
                    model_name=embedding.embedding_model,
                    dimension=embedding.embedding_dimension,
                    vector=list(embedding.embedding),
                )

                results.append(
                    RetrievalResult(
                        chunk=rag_chunk,
                        score=float(score),
                        embeddings=[rag_embedding],
                    ),
                )

        except Exception as exc:
            logger.exception(
                "Failed to map PGVector results to RAG models.",
                extra={
                    "result_count": len(rows),
                    "embedding_model": embedding_model,
                },
            )

            raise RAGError(
                message="Failed to map PGVector retrieval results.",
            ) from exc

        logger.debug(
            "PGVector retrieval completed.",
            extra={
                "top_k": top_k,
                "result_count": len(results),
                "embedding_model": embedding_model,
            },
        )

        return results
