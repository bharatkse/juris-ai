"""
Knowledge chunk embedding repository.

Provides persistence operations for embedding representations of
knowledge chunks.

A single KnowledgeChunk may have multiple embedding representations,
one for each embedding model.

For example:

    KnowledgeChunk
        ├── bge-small-en-v1.5
        ├── embedding-model-b
        └── embedding-model-c

This repository owns embedding persistence and vector similarity
operations. It does not own textual chunk lifecycle.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.knowledge_chunk import (
    KnowledgeChunk,
)
from adapters.persistence.sqlalchemy.models.knowledge_embedding import (
    KnowledgeEmbedding,
)


class KnowledgeEmbeddingRepository:
    """
    Repository for knowledge chunk embedding representations.

    The identity of an embedding representation is:

        (chunk_id, embedding_model)

    This allows the same textual chunk to be embedded by multiple
    models.
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

    async def get_by_id(
        self,
        *,
        embedding_id: str,
    ) -> KnowledgeEmbedding | None:
        """
        Retrieve an embedding representation by identifier.
        """

        result = await self._session.execute(
            select(KnowledgeEmbedding).where(
                KnowledgeEmbedding.id == embedding_id,
            ),
        )

        return result.scalar_one_or_none()

    async def get_by_chunk_and_model(
        self,
        *,
        chunk_id: str,
        embedding_model: str,
    ) -> KnowledgeEmbedding | None:
        """
        Retrieve an embedding for a specific chunk and model.
        """

        result = await self._session.execute(
            select(KnowledgeEmbedding).where(
                KnowledgeEmbedding.chunk_id == chunk_id,
                KnowledgeEmbedding.embedding_model == embedding_model,
            ),
        )

        return result.scalar_one_or_none()

    async def list_by_chunk_id(
        self,
        *,
        chunk_id: str,
    ) -> Sequence[KnowledgeEmbedding]:
        """
        Retrieve all embedding representations for a chunk.
        """

        result = await self._session.execute(
            select(KnowledgeEmbedding)
            .where(
                KnowledgeEmbedding.chunk_id == chunk_id,
            )
            .order_by(
                KnowledgeEmbedding.created_at,
            ),
        )

        return result.scalars().all()

    async def create(
        self,
        *,
        chunk_id: str,
        embedding_model: str,
        vector: list[float],
    ) -> KnowledgeEmbedding:
        """
        Create an embedding representation.

        Args:
            chunk_id:
                KnowledgeChunk identifier.

            embedding_model:
                Model that generated the vector.

            vector:
                Vector representation.

        Returns:
            Newly created KnowledgeEmbedding entity.
        """

        entity = KnowledgeEmbedding(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            embedding_dimension=len(vector),
            embedding=vector,
        )

        self._session.add(entity)

        await self._session.flush()

        return entity

    async def update(
        self,
        *,
        embedding: KnowledgeEmbedding,
        vector: list[float],
    ) -> KnowledgeEmbedding:
        """
        Update an existing embedding representation.

        The embedding model is not changed because it forms part of
        the representation identity.
        """

        embedding.embedding = vector
        embedding.embedding_dimension = len(vector)

        await self._session.flush()

        return embedding

    async def upsert(
        self,
        *,
        chunk_id: str,
        embedding_model: str,
        vector: list[float],
    ) -> KnowledgeEmbedding:
        """
        Create or update an embedding representation.

        The (chunk_id, embedding_model) pair uniquely identifies the
        representation.
        """

        existing = await self.get_by_chunk_and_model(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
        )

        if existing is not None:
            return await self.update(
                embedding=existing,
                vector=vector,
            )

        return await self.create(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            vector=vector,
        )

    async def delete_by_chunk_id(
        self,
        *,
        chunk_id: str,
    ) -> int:
        """
        Delete all embeddings belonging to a chunk.
        """

        result = await self._session.execute(
            delete(KnowledgeEmbedding).where(
                KnowledgeEmbedding.chunk_id == chunk_id,
            ),
        )

        await self._session.flush()

        return result.rowcount or 0

    async def delete_by_model(
        self,
        *,
        embedding_model: str,
    ) -> int:
        """
        Delete all embeddings generated by an embedding model.
        """

        result = await self._session.execute(
            delete(KnowledgeEmbedding).where(
                KnowledgeEmbedding.embedding_model == embedding_model,
            ),
        )

        await self._session.flush()

        return result.rowcount or 0

    async def vector_search(
        self,
        *,
        vector: list[float],
        embedding_model: str,
        top_k: int,
        allowed_knowledge_source_ids: set[str] | None = None,
    ) -> list[tuple[KnowledgeEmbedding, float]]:
        """
        Search embedding representations using cosine similarity.

        Only vectors produced by the requested embedding model are
        considered. This prevents vectors from different embedding
        spaces from being compared incorrectly.

        Args:
            vector:
                Query embedding.

            embedding_model:
                Embedding model that produced the query vector.

            top_k:
                Maximum number of results.

            allowed_knowledge_source_ids:
                Optional knowledge-source scope restriction.

        Returns:
            Matching KnowledgeEmbedding entities with cosine
            similarity scores.
        """

        statement = select(
            KnowledgeEmbedding,
            (
                1
                - KnowledgeEmbedding.embedding.cosine_distance(
                    vector,
                )
            ).label("score"),
        ).where(
            KnowledgeEmbedding.embedding_model == embedding_model,
        )

        if allowed_knowledge_source_ids:
            statement = statement.join(
                KnowledgeEmbedding.chunk,
            ).where(
                KnowledgeEmbedding.chunk.has(
                    KnowledgeChunk.knowledge_source_id.in_(
                        allowed_knowledge_source_ids,
                    ),
                ),
            )

        statement = statement.order_by(
            KnowledgeEmbedding.embedding.cosine_distance(
                vector,
            ),
        ).limit(top_k)

        result = await self._session.execute(statement)

        return [
            (
                entity,
                float(score),
            )
            for entity, score in result.all()
        ]
