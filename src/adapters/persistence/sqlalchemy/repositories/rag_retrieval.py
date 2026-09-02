"""
RAG retrieval repository.

Read-only persistence adapter for the RAG retrieval pipeline.

Persistence model:

    DocumentChunk
        |
        └── DocumentChunkEmbedding
                ├── embedding_model
                ├── embedding_dimension
                └── embedding

The repository retrieves SQLAlchemy persistence entities only.

Responsibilities:

    - vector similarity search
    - keyword/full-text search
    - embedding-model filtering
    - source filtering
    - PostgreSQL-side ranking
    - top-K limiting
    - eager loading of required relationships
    - streaming large result sets

It does NOT:

    - create or update documents
    - persist chunks
    - persist embeddings
    - change document status
    - delete documents
    - manage document lifecycle
    - generate embeddings
    - chunk text
    - rerank results
    - call an LLM
    - access StorageClient
    - return DTOs

Repository conventions:

    - Return SQLAlchemy entities.
    - Never return DTOs or dictionaries.
    - Keep database filtering/ranking inside PostgreSQL.
    - Avoid N+1 queries.
    - Return the actual embedding representation used for vector
      retrieval.
    - Return retrieval scores, not raw vector distances.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from adapters.persistence.sqlalchemy.models.document_chunk import (
    DocumentChunk,
)
from adapters.persistence.sqlalchemy.models.document_chunk_embedding import (
    DocumentChunkEmbedding,
)


class RAGRetrievalRepository:
    """
    Read-only repository for persisted RAG representations.

    Vector retrieval operates on DocumentChunkEmbedding because the
    vector belongs to the embedding representation, not directly to
    DocumentChunk.

    Vector-search results contain:

        DocumentChunkEmbedding
        retrieval score

    The matched chunk is available through:

        DocumentChunkEmbedding.chunk

    Keyword retrieval operates directly on DocumentChunk because the
    PostgreSQL full-text representation belongs to the textual chunk.

    Keyword-search results contain:

        DocumentChunk
        retrieval score
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        """
        Initialize the repository.

        Args:
            session:
                Active asynchronous SQLAlchemy session.
        """

        self._session = session

    async def vector_search(
        self,
        *,
        vector: list[float],
        top_k: int,
        embedding_model: str,
        source_ids: set[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[
        tuple[
            DocumentChunkEmbedding,
            float,
        ]
    ]:
        """
        Retrieve embedding representations using vector similarity.

        PostgreSQL performs:

            - vector similarity calculation
            - embedding-model filtering
            - optional source filtering
            - ranking
            - top-K limiting

        The returned embedding entity has its associated
        DocumentChunk eagerly loaded through the `chunk` relationship.

        Raw pgvector distance is not returned.

        The retrieval score is:

            1 - cosine_distance

        A higher score therefore represents a more similar result.

        Args:
            vector:
                Query embedding vector.

            top_k:
                Maximum number of results.

            embedding_model:
                Embedding model that produced the query vector.

            source_ids:
                Optional set of source/document identifiers restricting
                the search scope.

        Returns:
            List of:

                (
                    DocumentChunkEmbedding,
                    similarity_score,
                )
        """

        if not vector:
            return []

        if top_k <= 0:
            return []

        if not embedding_model.strip():
            return []

        cosine_distance = DocumentChunkEmbedding.embedding.cosine_distance(
            vector,
        )

        similarity_score = (1 - cosine_distance).label("score")

        statement: Select[Any] = (
            select(
                DocumentChunkEmbedding,
                similarity_score,
            )
            .options(
                joinedload(
                    DocumentChunkEmbedding.chunk,
                ),
            )
            .where(
                DocumentChunkEmbedding.embedding_model == embedding_model,
            )
        )

        if source_ids is not None:
            statement = statement.where(
                DocumentChunkEmbedding.chunk.has(
                    DocumentChunk.document_id.in_(source_ids),
                ),
            )

        if metadata_filters:
            source_id = metadata_filters.get("source_id")

            if source_id is not None:
                statement = statement.where(
                    DocumentChunkEmbedding.chunk.has(
                        DocumentChunk.chunk_metadata["source_id"].as_string() == source_id,
                    ),
                )

        statement = statement.order_by(
            cosine_distance.asc(),
        ).limit(top_k)

        result = await self._session.execute(
            statement,
        )

        return [
            (
                embedding,
                float(score),
            )
            for embedding, score in result.unique().all()
        ]

    async def keyword_search(
        self,
        *,
        query: str,
        top_k: int,
        source_ids: set[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[
        tuple[
            DocumentChunk,
            float,
        ]
    ]:
        """
        Retrieve chunks using PostgreSQL full-text search.

        PostgreSQL performs:

            - query parsing
            - text matching
            - relevance scoring
            - optional source filtering
            - ordering
            - top-K limiting

        Keyword indexing is derived from DocumentChunk.text through
        the persisted PostgreSQL text_tsv representation.

        No separate keyword/BM25 persistence entity is required.

        DocumentChunk.embeddings is eagerly loaded so downstream RAG
        processing can access available embedding representations
        without causing N+1 queries.

        Args:
            query:
                User keyword/full-text search query.

            top_k:
                Maximum number of results.

            source_ids:
                Optional set of source/document identifiers restricting
                the search scope.

        Returns:
            List of:

                (
                    DocumentChunk,
                    keyword_score,
                )
        """

        if not query.strip():
            return []

        if top_k <= 0:
            return []

        ts_query = func.websearch_to_tsquery(
            "english",
            query,
        )

        score = func.ts_rank(
            DocumentChunk.text_tsv,
            ts_query,
        ).label("score")

        statement: Select[Any] = (
            select(
                DocumentChunk,
                score,
            )
            .options(
                selectinload(
                    DocumentChunk.embeddings,
                ),
            )
            .where(
                DocumentChunk.text_tsv.op("@@")(
                    ts_query,
                ),
            )
        )

        if source_ids is not None:
            statement = statement.where(
                DocumentChunk.document_id.in_(source_ids),
            )

        if metadata_filters:
            source_id = metadata_filters.get("source_id")
            if source_id is not None:
                if isinstance(source_id, set):
                    statement = statement.where(
                        DocumentChunk.chunk_metadata["source_id"]
                        .as_string()
                        .in_(
                            source_id,
                        ),
                    )
                else:
                    statement = statement.where(
                        DocumentChunk.chunk_metadata["source_id"].as_string() == source_id,
                    )

        statement = statement.order_by(
            score.desc(),
        ).limit(top_k)

        result = await self._session.execute(
            statement,
        )

        return [
            (
                chunk,
                float(score),
            )
            for chunk, score in result.unique().all()
        ]

    async def stream_vector_search(
        self,
        *,
        vector: list[float],
        top_k: int,
        embedding_model: str,
        source_ids: set[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> AsyncIterator[
        tuple[
            DocumentChunkEmbedding,
            float,
        ]
    ]:
        """
        Stream vector-search results.

        The matched DocumentChunkEmbedding is yielded with its
        associated DocumentChunk eagerly loaded.

        Raw pgvector distance is not exposed.

        Yields:
            (
                DocumentChunkEmbedding,
                similarity_score,
            )
        """

        if not vector:
            return

        if top_k <= 0:
            return

        if not embedding_model.strip():
            return

        cosine_distance = DocumentChunkEmbedding.embedding.cosine_distance(
            vector,
        )

        similarity_score = (1 - cosine_distance).label("score")

        statement: Select[Any] = (
            select(
                DocumentChunkEmbedding,
                similarity_score,
            )
            .options(
                joinedload(
                    DocumentChunkEmbedding.chunk,
                ),
            )
            .where(
                DocumentChunkEmbedding.embedding_model == embedding_model,
            )
        )

        if source_ids is not None:
            statement = statement.where(
                DocumentChunkEmbedding.chunk.has(
                    DocumentChunk.document_id.in_(source_ids),
                ),
            )

        statement = statement.order_by(
            cosine_distance.asc(),
        ).limit(top_k)

        result = await self._session.stream(
            statement,
        )

        async for embedding, score in result.unique():
            yield (
                embedding,
                float(score),
            )

    async def stream_keyword_search(
        self,
        *,
        query: str,
        top_k: int,
        source_ids: set[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> AsyncIterator[
        tuple[
            DocumentChunk,
            float,
        ]
    ]:
        """
        Stream PostgreSQL full-text-search results.

        DocumentChunk.embeddings is eagerly loaded so downstream
        relationship access does not cause N+1 queries.

        Yields:
            (
                DocumentChunk,
                keyword_score,
            )
        """

        if not query.strip():
            return

        if top_k <= 0:
            return

        ts_query = func.websearch_to_tsquery(
            "english",
            query,
        )

        score = func.ts_rank(
            DocumentChunk.text_tsv,
            ts_query,
        ).label("score")

        statement: Select[Any] = (
            select(
                DocumentChunk,
                score,
            )
            .options(
                selectinload(
                    DocumentChunk.embeddings,
                ),
            )
            .where(
                DocumentChunk.text_tsv.op("@@")(
                    ts_query,
                ),
            )
        )

        if source_ids is not None:
            statement = statement.where(
                DocumentChunk.document_id.in_(source_ids),
            )

        statement = statement.order_by(
            score.desc(),
        ).limit(top_k)

        result = await self._session.stream(
            statement,
        )

        async for chunk, score in result.unique():
            yield (
                chunk,
                float(score),
            )
