"""
RAG retrieval repository.

Read-only persistence adapter for the RAG retrieval pipeline.

Persistence model:

    KnowledgeSource
        |
        └── KnowledgeChunk
                |
                └── KnowledgeEmbedding
                        ├── embedding_model
                        ├── embedding_dimension
                        └── embedding

The repository retrieves SQLAlchemy persistence entities only.

Responsibilities:

    - vector similarity search
    - keyword/full-text search
    - embedding-model filtering
    - knowledge-source filtering
    - metadata filtering
    - PostgreSQL-side ranking
    - top-K limiting
    - eager loading of required relationships
    - streaming large result sets

It does NOT:

    - create or update KnowledgeSource entities
    - persist KnowledgeChunk entities
    - persist KnowledgeEmbedding entities
    - change knowledge-source status
    - delete knowledge sources
    - manage knowledge lifecycle
    - generate embeddings
    - chunk text
    - rerank results
    - call an LLM
    - access StorageClient
    - construct RAGResult objects
    - return DTOs

Repository conventions:

    - Return SQLAlchemy entities.
    - Never return DTOs or dictionaries.
    - Keep database filtering and ranking inside PostgreSQL.
    - Avoid N+1 queries.
    - Return retrieval scores rather than raw vector distances.
    - Keep relational source filtering separate from metadata filtering.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from adapters.persistence.sqlalchemy.models.knowledge_chunk import (
    KnowledgeChunk,
)
from adapters.persistence.sqlalchemy.models.knowledge_embedding import (
    KnowledgeEmbedding,
)


class RAGRetrievalRepository:
    """
    Read-only repository for persisted RAG representations.

    This repository is responsible only for querying the persistence
    representation used by the RAG retrieval pipeline.

    The persistence hierarchy is:

        KnowledgeSource
            |
            └── KnowledgeChunk
                    |
                    └── KnowledgeEmbedding

    Vector retrieval operates on KnowledgeEmbedding because the vector
    belongs to a particular embedding representation.

    The associated KnowledgeChunk is eagerly loaded through the
    KnowledgeEmbedding.chunk relationship.

    Keyword retrieval operates directly on KnowledgeChunk because
    PostgreSQL full-text-search data is derived from KnowledgeChunk.text
    and persisted in KnowledgeChunk.text_tsv.

    The repository intentionally does not perform higher-level RAG
    responsibilities such as:

        - query transformation
        - embedding generation
        - hybrid retrieval orchestration
        - reciprocal-rank fusion
        - cross-encoder reranking
        - context assembly
        - RAGResult construction
        - LLM invocation

    Those responsibilities belong to higher layers of the RAG pipeline.

    All returned objects are SQLAlchemy persistence entities together
    with database-computed retrieval scores.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        """
        Initialize the RAG retrieval repository.

        Args:
            session:
                Active asynchronous SQLAlchemy session used for all
                database operations.
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
    ) -> list[tuple[KnowledgeEmbedding, float]]:
        """
        Retrieve persisted embedding representations using vector similarity.

        The vector search is executed entirely by PostgreSQL/pgvector.

        PostgreSQL performs:

            - embedding-model filtering
            - optional KnowledgeSource filtering
            - optional metadata filtering
            - cosine-distance calculation
            - similarity-score calculation
            - ranking
            - top-K limiting

        The query vector is compared against KnowledgeEmbedding.embedding.

        Raw pgvector cosine distance is not exposed to callers.

        The returned score is calculated as:

            similarity_score = 1 - cosine_distance

        Therefore:

            higher score  -> more similar
            lower score   -> less similar

        The associated KnowledgeChunk is eagerly loaded through
        KnowledgeEmbedding.chunk to avoid an N+1 query when the caller
        accesses the matched chunk.

        Source filtering uses the authoritative relationship:

            KnowledgeChunk.knowledge_source_id

        Metadata filtering is handled separately through
        KnowledgeChunk.chunk_metadata.

        This method performs retrieval only. It does not perform
        reranking, RRF, context construction, or LLM invocation.

        Args:
            vector:
                Query embedding vector.

            top_k:
                Maximum number of embedding representations to return.

            embedding_model:
                Identifier of the embedding model that produced the
                query vector. Only persisted embeddings generated by
                this model are eligible for comparison.

            source_ids:
                Optional set of KnowledgeSource IDs restricting the
                retrieval scope.

            metadata_filters:
                Optional metadata constraints applied against
                KnowledgeChunk.chunk_metadata.

        Returns:
            A list of tuples containing:

                (
                    KnowledgeEmbedding,
                    similarity_score,
                )

            The list is ordered by descending vector similarity.
        """

        if not vector:
            return []

        if top_k <= 0:
            return []

        if not embedding_model.strip():
            return []

        cosine_distance = KnowledgeEmbedding.embedding.cosine_distance(
            vector,
        )

        similarity_score = (1 - cosine_distance).label("score")

        statement: Select[Any] = (
            select(
                KnowledgeEmbedding,
                similarity_score,
            )
            .options(
                joinedload(
                    KnowledgeEmbedding.chunk,
                ),
            )
            .where(
                KnowledgeEmbedding.embedding_model == embedding_model,
            )
        )

        statement = self._apply_source_filter(
            statement=statement,
            source_ids=source_ids,
        )

        statement = self._apply_metadata_filters(
            statement=statement,
            metadata_filters=metadata_filters,
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
    ) -> list[tuple[KnowledgeChunk, float]]:
        """
        Retrieve knowledge chunks using PostgreSQL full-text search.

        Keyword retrieval operates directly on KnowledgeChunk because
        the PostgreSQL full-text representation is stored in:

            KnowledgeChunk.text_tsv

        PostgreSQL performs:

            - query parsing
            - full-text matching
            - relevance scoring
            - optional KnowledgeSource filtering
            - optional metadata filtering
            - relevance ordering
            - top-K limiting

        Relevance is calculated using PostgreSQL ts_rank.

        KnowledgeChunk.embeddings is eagerly loaded using selectinload
        so downstream processing can access persisted embedding
        representations without causing N+1 queries.

        Source filtering uses:

            KnowledgeChunk.knowledge_source_id

        Metadata filtering uses:

            KnowledgeChunk.chunk_metadata

        This method performs keyword retrieval only. It does not perform
        vector retrieval, RRF, reranking, context construction, or
        LLM invocation.

        Args:
            query:
                User-provided keyword/full-text search query.

            top_k:
                Maximum number of chunks to return.

            source_ids:
                Optional set of KnowledgeSource IDs restricting the
                retrieval scope.

            metadata_filters:
                Optional metadata constraints applied against
                KnowledgeChunk.chunk_metadata.

        Returns:
            A list of tuples containing:

                (
                    KnowledgeChunk,
                    keyword_score,
                )

            The list is ordered by descending PostgreSQL full-text
            relevance score.
        """

        if not query.strip():
            return []

        if top_k <= 0:
            return []

        ts_query = self._build_keyword_ts_query(
            query,
        )

        score = func.ts_rank(
            KnowledgeChunk.text_tsv,
            ts_query,
        ).label("score")

        statement: Select[Any] = (
            select(
                KnowledgeChunk,
                score,
            )
            .options(
                selectinload(
                    KnowledgeChunk.embeddings,
                ),
            )
            .where(
                KnowledgeChunk.text_tsv.op("@@")(
                    ts_query,
                ),
            )
        )

        statement = self._apply_source_filter(
            statement=statement,
            source_ids=source_ids,
        )

        statement = self._apply_metadata_filters(
            statement=statement,
            metadata_filters=metadata_filters,
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
    ) -> AsyncIterator[tuple[KnowledgeEmbedding, float]]:
        """
        Stream vector-search results asynchronously.

        This method has the same retrieval semantics as vector_search()
        but streams database results instead of materializing the entire
        result set in memory.

        PostgreSQL performs:

            - embedding-model filtering
            - optional KnowledgeSource filtering
            - optional metadata filtering
            - cosine-distance calculation
            - similarity-score calculation
            - ranking
            - top-K limiting

        The associated KnowledgeChunk is eagerly loaded through
        KnowledgeEmbedding.chunk.

        Raw vector distance is not exposed.

        The returned score is:

            similarity_score = 1 - cosine_distance

        A higher score indicates greater vector similarity.

        Args:
            vector:
                Query embedding vector.

            top_k:
                Maximum number of results to stream.

            embedding_model:
                Identifier of the embedding model that produced the
                query vector.

            source_ids:
                Optional set of KnowledgeSource IDs restricting the
                retrieval scope.

            metadata_filters:
                Optional metadata constraints applied against
                KnowledgeChunk.chunk_metadata.

        Yields:
            Tuples containing:

                (
                    KnowledgeEmbedding,
                    similarity_score,
                )

            Results are yielded in descending similarity order.
        """

        if not vector:
            return

        if top_k <= 0:
            return

        if not embedding_model.strip():
            return

        cosine_distance = KnowledgeEmbedding.embedding.cosine_distance(
            vector,
        )

        similarity_score = (1 - cosine_distance).label("score")

        statement: Select[Any] = (
            select(
                KnowledgeEmbedding,
                similarity_score,
            )
            .options(
                joinedload(
                    KnowledgeEmbedding.chunk,
                ),
            )
            .where(
                KnowledgeEmbedding.embedding_model == embedding_model,
            )
        )

        statement = self._apply_source_filter(
            statement=statement,
            source_ids=source_ids,
        )

        statement = self._apply_metadata_filters(
            statement=statement,
            metadata_filters=metadata_filters,
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
    ) -> AsyncIterator[tuple[KnowledgeChunk, float]]:
        """
        Stream PostgreSQL full-text-search results asynchronously.

        This method has the same retrieval semantics as keyword_search()
        but streams database results instead of materializing the entire
        result set in memory.

        PostgreSQL performs:

            - full-text query matching
            - relevance scoring
            - optional KnowledgeSource filtering
            - optional metadata filtering
            - ranking
            - top-K limiting

        KnowledgeChunk.embeddings is eagerly loaded using selectinload
        so downstream processing can access embedding representations
        without triggering N+1 relationship queries.

        Source filtering uses:

            KnowledgeChunk.knowledge_source_id

        Metadata filtering uses:

            KnowledgeChunk.chunk_metadata

        Args:
            query:
                User-provided keyword/full-text search query.

            top_k:
                Maximum number of chunks to stream.

            source_ids:
                Optional set of KnowledgeSource IDs restricting the
                retrieval scope.

            metadata_filters:
                Optional metadata constraints applied against
                KnowledgeChunk.chunk_metadata.

        Yields:
            Tuples containing:

                (
                    KnowledgeChunk,
                    keyword_score,
                )

            Results are yielded in descending PostgreSQL full-text
            relevance order.
        """

        if not query.strip():
            return

        if top_k <= 0:
            return

        ts_query = self._build_keyword_ts_query(
            query,
        )

        score = func.ts_rank(
            KnowledgeChunk.text_tsv,
            ts_query,
        ).label("score")

        statement: Select[Any] = (
            select(
                KnowledgeChunk,
                score,
            )
            .options(
                selectinload(
                    KnowledgeChunk.embeddings,
                ),
            )
            .where(
                KnowledgeChunk.text_tsv.op("@@")(
                    ts_query,
                ),
            )
        )

        statement = self._apply_source_filter(
            statement=statement,
            source_ids=source_ids,
        )

        statement = self._apply_metadata_filters(
            statement=statement,
            metadata_filters=metadata_filters,
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

    @staticmethod
    def _apply_source_filter(
        *,
        statement: Select[Any],
        source_ids: set[str] | None,
    ) -> Select[Any]:
        """
        Apply relational KnowledgeSource filtering.

        The authoritative relationship between a knowledge chunk and
        its source is:

            KnowledgeChunk.knowledge_source_id

        Therefore, source_ids are always matched against
        KnowledgeChunk.knowledge_source_id.

        This method intentionally does not use:

            KnowledgeChunk.chunk_metadata["source_id"]

        because metadata is not the authoritative relational
        representation of the KnowledgeSource relationship.

        Args:
            statement:
                SQLAlchemy SELECT statement being constructed.

            source_ids:
                Optional set of KnowledgeSource IDs restricting the
                retrieval scope.

        Returns:
            The original statement when source_ids is None or empty;
            otherwise, the statement with a KnowledgeSource filter.
        """

        if not source_ids:
            return statement

        return statement.where(
            KnowledgeChunk.knowledge_source_id.in_(
                source_ids,
            ),
        )

    @staticmethod
    def _apply_metadata_filters(
        *,
        statement: Select[Any],
        metadata_filters: dict[str, Any] | None,
    ) -> Select[Any]:
        """
        Apply supported KnowledgeChunk metadata filters.

        Metadata is stored in:

            KnowledgeChunk.chunk_metadata

        Metadata filtering is intentionally separate from relational
        KnowledgeSource filtering.

        Currently supported:

            source_id:
                Filters against the metadata value stored at
                `chunk_metadata["source_id"]`.

        Supported source_id values are:

            - str
            - set[str]
            - list[str]
            - tuple[str, ...]

        This method only applies filters explicitly supported by this
        repository. Unknown metadata keys are ignored rather than
        dynamically generating arbitrary SQL expressions.

        Args:
            statement:
                SQLAlchemy SELECT statement being constructed.

            metadata_filters:
                Optional mapping containing metadata constraints.

        Returns:
            The SQLAlchemy SELECT statement with supported metadata
            constraints applied.
        """

        if not metadata_filters:
            return statement

        source_id = metadata_filters.get(
            "source_id",
        )

        if source_id is None:
            return statement

        metadata_source_id = KnowledgeChunk.chunk_metadata["source_id"].as_string()

        if isinstance(
            source_id,
            (set | list | tuple),
        ):
            return statement.where(
                metadata_source_id.in_(
                    source_id,
                ),
            )

        return statement.where(
            metadata_source_id == source_id,
        )

    @staticmethod
    def _build_keyword_ts_query(
        query: str,
    ):
        """
        Build a PostgreSQL full-text-search query.

        The input query is split into individual terms. Surrounding
        punctuation is removed from each term, and the resulting terms
        are combined using OR semantics.

        For example:

            contract termination notice

        becomes conceptually:

            contract OR termination OR notice

        The final expression is passed to PostgreSQL's
        websearch_to_tsquery using the `english` text-search
        configuration.

        The `english` configuration matches the configuration used by
        KnowledgeChunk.text_tsv:

            to_tsvector('english', text)

        If no usable terms can be extracted, the original query is
        passed directly to websearch_to_tsquery.

        Args:
            query:
                User-provided full-text-search query.

        Returns:
            SQLAlchemy SQL function expression representing a PostgreSQL
            tsquery.
        """

        terms = [
            term.strip(
                ".,?!:;()[]{}\"'",
            )
            for term in query.split()
            if term.strip(
                ".,?!:;()[]{}\"'",
            )
        ]

        if not terms:
            return func.websearch_to_tsquery(
                "english",
                query,
            )

        keyword_query = " OR ".join(
            terms,
        )

        return func.websearch_to_tsquery(
            "english",
            keyword_query,
        )
