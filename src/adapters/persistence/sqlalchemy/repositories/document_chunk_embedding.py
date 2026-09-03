"""
Document chunk embedding repository.

Provides persistence operations for embedding representations of
document chunks.

A single textual DocumentChunk may have multiple embedding
representations, one for each embedding model.

For example:

    DocumentChunk
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

from adapters.persistence.sqlalchemy.models.document_chunk import (
    DocumentChunk,
)
from adapters.persistence.sqlalchemy.models.document_chunk_embedding import (
    DocumentChunkEmbedding,
)


class DocumentChunkEmbeddingRepository:
    """
    Repository for document chunk embedding representations.

    The identity of an embedding representation is:

        (chunk_id, embedding_model)

    This allows the same textual chunk to be embedded by multiple
    models and later compared during RAG evaluation.
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
    ) -> DocumentChunkEmbedding | None:
        """
        Retrieve an embedding representation by identifier.

        Args:
            embedding_id:
                Embedding entity identifier.

        Returns:
            The matching embedding, or None when it does not exist.
        """

        result = await self._session.execute(
            select(DocumentChunkEmbedding).where(
                DocumentChunkEmbedding.id == embedding_id,
            ),
        )

        return result.scalar_one_or_none()

    async def get_by_chunk_and_model(
        self,
        *,
        chunk_id: str,
        embedding_model: str,
    ) -> DocumentChunkEmbedding | None:
        """
        Retrieve an embedding for a specific chunk and model.

        Args:
            chunk_id:
                DocumentChunk identifier.

            embedding_model:
                Name of the embedding model.

        Returns:
            Matching embedding representation, or None.
        """

        result = await self._session.execute(
            select(DocumentChunkEmbedding).where(
                DocumentChunkEmbedding.chunk_id == chunk_id,
                DocumentChunkEmbedding.embedding_model == embedding_model,
            ),
        )

        return result.scalar_one_or_none()

    async def list_by_chunk_id(
        self,
        *,
        chunk_id: str,
    ) -> Sequence[DocumentChunkEmbedding]:
        """
        Retrieve all embedding representations for a chunk.

        Args:
            chunk_id:
                DocumentChunk identifier.

        Returns:
            All embeddings associated with the chunk.
        """

        result = await self._session.execute(
            select(DocumentChunkEmbedding)
            .where(
                DocumentChunkEmbedding.chunk_id == chunk_id,
            )
            .order_by(
                DocumentChunkEmbedding.created_at,
            ),
        )

        return result.scalars().all()

    async def create(
        self,
        *,
        chunk_id: str,
        embedding_model: str,
        embedding: list[float],
    ) -> DocumentChunkEmbedding:
        """
        Create an embedding representation.

        Args:
            chunk_id:
                DocumentChunk identifier.

            embedding_model:
                Model that generated the vector.

            embedding:
                Vector representation.

        Returns:
            Newly created embedding entity.
        """

        entity = DocumentChunkEmbedding(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            embedding_dimension=len(embedding),
            embedding=embedding,
        )

        self._session.add(entity)

        await self._session.flush()

        return entity

    async def update(
        self,
        *,
        embedding: DocumentChunkEmbedding,
        vector: list[float],
    ) -> DocumentChunkEmbedding:
        """
        Update an existing embedding representation.

        The embedding model is not changed because it forms part of
        the representation identity.

        Args:
            embedding:
                Existing embedding entity.

            vector:
                New vector representation.

        Returns:
            Updated embedding entity.
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
    ) -> DocumentChunkEmbedding:
        """
        Create or update an embedding representation.

        The `(chunk_id, embedding_model)` pair uniquely identifies the
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
            embedding=vector,
        )

    async def delete_by_chunk_id(
        self,
        *,
        chunk_id: str,
    ) -> int:
        """
        Delete all embeddings belonging to a chunk.

        Args:
            chunk_id:
                DocumentChunk identifier.

        Returns:
            Number of deleted embeddings.
        """

        result = await self._session.execute(
            delete(DocumentChunkEmbedding).where(
                DocumentChunkEmbedding.chunk_id == chunk_id,
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

        Args:
            embedding_model:
                Model whose representations should be removed.

        Returns:
            Number of deleted embedding records.
        """

        result = await self._session.execute(
            delete(DocumentChunkEmbedding).where(
                DocumentChunkEmbedding.embedding_model == embedding_model,
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
        allowed_document_ids: set[str] | None = None,
    ) -> list[tuple[DocumentChunkEmbedding, float]]:
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

            allowed_document_ids:
                Optional document scope restriction.

        Returns:
            Matching embedding entities with cosine similarity scores.
        """

        statement = select(
            DocumentChunkEmbedding,
            (
                1
                - DocumentChunkEmbedding.embedding.cosine_distance(
                    vector,
                )
            ).label("score"),
        ).where(
            DocumentChunkEmbedding.embedding_model == embedding_model,
        )

        if allowed_document_ids:
            statement = statement.join(
                DocumentChunkEmbedding.chunk,
            ).where(
                DocumentChunkEmbedding.chunk.has(
                    DocumentChunk.document_id.in_(allowed_document_ids),
                ),
            )

        statement = statement.order_by(
            DocumentChunkEmbedding.embedding.cosine_distance(
                vector,
            ),
        ).limit(top_k)

        result = await self._session.execute(
            statement,
        )

        return [
            (
                entity,
                float(score),
            )
            for entity, score in result.all()
        ]
