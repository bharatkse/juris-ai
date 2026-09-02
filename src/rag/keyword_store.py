"""
PostgreSQL keyword-search adapter for the RAG pipeline.

Infrastructure adapter between the RAG keyword-search capability and
the PostgreSQL full-text-search persistence implementation.

RAG domain models live in:
    rag.models

Capability contract lives in:
    rag.protocols.keyword

Persistence and database-specific search logic remain inside the
persistence repository layer.

This adapter is responsible only for:

    - opening the persistence session
    - invoking keyword-search persistence operations
    - translating persistence entities into RAG domain models

It does NOT:

    - create or update document chunks
    - create or update embeddings
    - manage document lifecycle
    - orchestrate write repositories
    - manage transactions
    - generate embeddings
    - chunk documents
    - sanitize content
    - perform reranking
    - call an LLM
    - access StorageClient
"""

from __future__ import annotations

from typing import Any

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.rag_retrieval import (
    RAGRetrievalRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from core.exceptions.rag import RAGError
from rag.models import (
    Chunk,
    EmbeddingRepresentation,
    RetrievalResult,
)
from rag.protocols.keyword import KeywordStoreProtocol

logger = get_logger(__name__)


class PostgresKeywordStore(KeywordStoreProtocol):
    """
    PostgreSQL implementation of keyword-search retrieval.

    PostgreSQL full-text indexing is derived from DocumentChunk.text
    through the persisted text_tsv representation.

    No separate keyword-index persistence operation is required.
    """

    def __init__(self) -> None:
        """
        Initialize the PostgreSQL keyword-search adapter.
        """

        self._session_factory = session_factory

    async def query(
        self,
        *,
        query: str,
        top_k: int,
        allowed_source_ids: set[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve keyword-search candidates.

        PostgreSQL performs:

            - query parsing
            - full-text matching
            - relevance scoring
            - source filtering
            - ordering
            - top-K limiting

        The persistence repository is responsible for eager-loading
        any embedding representations required to construct complete
        RAG retrieval results.

        Args:
            query:
                User search query.

            top_k:
                Maximum number of results to return.

            allowed_source_ids:
                Optional source/document identifiers restricting
                the search scope.

        Returns:
            RAG retrieval results.

        Raises:
            RAGError:
                If retrieval or result mapping fails.
        """

        if not query.strip():
            return []

        if top_k <= 0:
            return []

        effective_metadata_filters = dict(
            metadata_filters or {},
        )

        if allowed_source_ids is not None:
            effective_metadata_filters["source_id"] = (
                next(
                    iter(allowed_source_ids),
                )
                if len(allowed_source_ids) == 1
                else None
            )

        try:
            async with self._session_factory() as session:
                repository = RAGRetrievalRepository(
                    session=session,
                )

                rows = await repository.keyword_search(
                    query=query,
                    top_k=top_k,
                    source_ids=None,
                    metadata_filters=effective_metadata_filters,
                )

        except RAGError:
            logger.exception(
                "PostgreSQL keyword retrieval failed.",
                extra={
                    "top_k": top_k,
                    "query_length": len(query),
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected PostgreSQL keyword retrieval failure.",
                extra={
                    "top_k": top_k,
                    "query_length": len(query),
                },
            )

            raise RAGError(
                message="Failed to retrieve keyword-search results.",
            ) from exc

        try:
            results: list[RetrievalResult] = []

            for chunk, score in rows:
                rag_chunk = Chunk(
                    id=chunk.id,
                    source_id=(chunk.chunk_metadata.get("source_id") or chunk.document_id),
                    text=chunk.text,
                    metadata=dict(
                        chunk.chunk_metadata or {},
                    ),
                )

                embeddings = [
                    EmbeddingRepresentation(
                        model_name=embedding.embedding_model,
                        dimension=embedding.embedding_dimension,
                        vector=list(embedding.embedding),
                    )
                    for embedding in chunk.embeddings
                ]

                results.append(
                    RetrievalResult(
                        chunk=rag_chunk,
                        score=float(score),
                        embeddings=embeddings,
                    ),
                )

        except Exception as exc:
            logger.exception(
                "Failed to map PostgreSQL keyword results to RAG models.",
                extra={
                    "result_count": len(rows),
                },
            )

            raise RAGError(
                message="Failed to map keyword-search results.",
            ) from exc

        logger.debug(
            "PostgreSQL keyword retrieval completed.",
            extra={
                "top_k": top_k,
                "result_count": len(results),
            },
        )

        return results
