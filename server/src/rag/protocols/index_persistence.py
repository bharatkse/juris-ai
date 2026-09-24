"""
RAG index persistence capability contract.

Defines the application-facing capability required to persist
RAG chunks together with their embedding representations.

Concrete implementations are responsible for coordinating the
persistence of:

    - textual document chunks
    - embedding representations

The contract intentionally contains no knowledge of:

    - SQLAlchemy
    - PostgreSQL
    - pgvector
    - repositories
    - document parsing
    - ingestion
    - retrieval
    - reranking
    - LLMs
"""

from __future__ import annotations

from typing import Protocol

from rag.models import Chunk


class RAGIndexPersistenceProtocol(Protocol):
    """
    Capability contract for persisting indexed RAG representations.

    Implementations coordinate persistence of a bounded batch of
    RAG chunks and their corresponding embedding vectors.

    Transaction management belongs to the concrete application
    persistence service.
    """

    async def persist(
        self,
        *,
        chunks: list[Chunk],
        vectors: list[list[float]],
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        """
        Persist RAG chunks and their embedding representations.

        Args:
            chunks:
                RAG-domain chunks to persist.

            vectors:
                Embedding vectors corresponding to the chunks.
                Vector order must match chunk order.

            embedding_model:
                Model used to generate the vectors.

            embedding_dimension:
                Dimension of every vector.

        Raises:
            RAGError:
                If persistence fails.
        """

        ...
