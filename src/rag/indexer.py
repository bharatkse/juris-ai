"""
RAG indexing orchestration.

Consumes streaming RAG-domain Chunk objects and indexes them into
the configured vector store.

Flow:

    Iterator[Chunk]
        ↓
    bounded batch
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
PostgreSQL FTS/BM25          pgvector

Keyword/BM25 retrieval is a read-only capability and is intentionally
not part of the indexing orchestration. PostgreSQL full-text/BM25
indexing is maintained from the persisted DocumentChunk representation.

This module does not:
    - parse documents
    - ingest documents
    - sanitize content
    - chunk documents
    - manage document lifecycle
    - coordinate keyword retrieval
    - perform retrieval
    - perform reranking
    - call an LLM
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from adapters.observability.logger import get_logger
from core.exceptions.rag import RAGError
from rag.models import Chunk, IndexedRepresentation
from rag.protocols.indexer import RAGIndexerProtocol

if TYPE_CHECKING:
    from rag.protocols.embedding_provider import EmbeddingProviderProtocol
    from rag.protocols.vector import VectorStoreProtocol

logger = get_logger(__name__)

DEFAULT_INDEX_BATCH_SIZE = 32


class RAGIndexer(RAGIndexerProtocol):
    """
    Stateless, bounded-batch RAG indexing orchestrator.

    The indexer is responsible for:

        - consuming RAG-domain chunks
        - batching chunks
        - generating embeddings
        - validating embeddings
        - delegating persistence to the vector-store capability

    The vector-store capability owns the application persistence
    boundary.

    Keyword/BM25 retrieval is intentionally excluded because it is
    a read-only retrieval capability.
    """

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProviderProtocol,
        vector_store: VectorStoreProtocol,
        batch_size: int = DEFAULT_INDEX_BATCH_SIZE,
    ) -> None:
        """
        Initialize the RAG indexing orchestrator.

        Args:
            embedding_provider:
                Provider responsible for generating embeddings.

            vector_store:
                Capability responsible for persisting indexed
                representations.

            batch_size:
                Maximum number of chunks processed in one batch.
        """

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero.",
            )

        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._batch_size = batch_size

    async def index(
        self,
        *,
        source_id: str,
        chunks: Iterable[Chunk],
    ) -> IndexedRepresentation:
        """
        Incrementally index a stream of chunks.

        Only one bounded batch is held in memory at a time.

        Args:
            source_id:
                Identifier of the source document being indexed.

            chunks:
                Iterable of RAG-domain chunks belonging to the source.

        Returns:
            Summary of the indexed representation.

        Raises:
            RAGError:
                If embedding generation or persistence fails.
        """

        if source_id and not source_id.strip():
            raise ValueError(
                "source_id must not be empty.",
            )

        metadata = self._embedding_provider.metadata

        chunk_count = 0
        batch: list[Chunk] = []

        try:
            for chunk in chunks:
                self._validate_chunk(
                    chunk=chunk,
                    source_id=source_id,
                )

                if not chunk.text.strip():
                    continue

                batch.append(chunk)

                if len(batch) >= self._batch_size:
                    processed_count = await self._index_batch(
                        batch=batch,
                        embedding_model=metadata.model_name,
                        embedding_dimension=metadata.dimension,
                    )

                    chunk_count += processed_count
                    batch.clear()

            if batch:
                processed_count = await self._index_batch(
                    batch=batch,
                    embedding_model=metadata.model_name,
                    embedding_dimension=metadata.dimension,
                )

                chunk_count += processed_count
                batch.clear()

        except RAGError:
            logger.exception(
                "RAG indexing failed.",
                extra={
                    "source_id": source_id,
                    "chunks_indexed": chunk_count,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error during RAG indexing.",
                extra={
                    "source_id": source_id,
                    "chunks_indexed": chunk_count,
                },
            )

            raise RAGError(
                message=f"Failed to index source '{source_id}'.",
            ) from exc

        logger.info(
            "RAG indexing completed.",
            extra={
                "source_id": source_id,
                "chunk_count": chunk_count,
                "embedding_model": metadata.model_name,
                "embedding_dimension": metadata.dimension,
            },
        )

        return IndexedRepresentation(
            source_id=source_id,
            chunk_count=chunk_count,
            embedding_model=metadata.model_name,
            embedding_dimension=metadata.dimension,
        )

    async def _index_batch(
        self,
        *,
        batch: list[Chunk],
        embedding_model: str,
        embedding_dimension: int,
    ) -> int:
        """
        Generate embeddings and persist one bounded batch.

        The vector store is the only persistence capability used by
        the indexing flow.

        Its implementation delegates to the application persistence
        service, which coordinates:

            - DocumentChunk persistence
            - DocumentChunkEmbedding persistence
            - transaction management

        Returns:
            Number of successfully indexed chunks.

        Raises:
            RAGError:
                If embedding generation or persistence fails.
        """

        if not batch:
            return 0

        try:
            texts = [chunk.text for chunk in batch]

            vectors = await self._embedding_provider.embed(
                texts=texts,
            )

            self._validate_embeddings(
                vectors=vectors,
                expected_count=len(batch),
                expected_dimension=embedding_dimension,
            )

            await self._vector_store.upsert(
                chunks=batch,
                vectors=vectors,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )

            logger.debug(
                "RAG indexing batch completed.",
                extra={
                    "batch_size": len(batch),
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                },
            )

            return len(batch)

        except RAGError:
            raise

        except Exception as exc:
            logger.exception(
                "Failed to index RAG batch.",
                extra={
                    "batch_size": len(batch),
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                },
            )

            raise RAGError(
                message="Failed to index RAG batch.",
            ) from exc

    @staticmethod
    def _validate_chunk(
        *,
        chunk: Chunk,
        source_id: str,
    ) -> None:
        """
        Validate that a chunk belongs to the current source.
        """

        if chunk.source_id != source_id:
            raise RAGError(
                message=(
                    "Chunk source mismatch: "
                    f"expected '{source_id}', "
                    f"received '{chunk.source_id}'."
                ),
            )

        if not chunk.id.strip():
            raise RAGError(
                message="Chunk id must not be empty.",
            )

    @staticmethod
    def _validate_embeddings(
        *,
        vectors: list[list[float]],
        expected_count: int,
        expected_dimension: int,
    ) -> None:
        """
        Validate embedding count and dimensionality before persistence.
        """

        if len(vectors) != expected_count:
            raise RAGError(
                message=(
                    "Embedding count mismatch: "
                    f"expected {expected_count}, "
                    f"received {len(vectors)}."
                ),
            )

        for vector in vectors:
            if len(vector) != expected_dimension:
                raise RAGError(
                    message=(
                        "Embedding dimension mismatch: "
                        f"expected {expected_dimension}, "
                        f"received {len(vector)}."
                    ),
                )
