"""
Knowledge chunk repository.

Provides persistence operations for textual knowledge chunks.

A KnowledgeChunk represents extracted textual content belonging to a
source document. Embedding representations are persisted separately
through KnowledgeEmbeddingRepository.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.knowledge_chunk import (
    KnowledgeChunk,
)


class KnowledgeChunkRepository:
    """
    Repository for persisted knowledge chunks.

    This repository intentionally has no knowledge of embeddings,
    embedding models, vector dimensions, or vector search.
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
        chunk_id: str,
    ) -> KnowledgeChunk | None:
        """
        Retrieve a knowledge chunk by identifier.

        Args:
            chunk_id:
                KnowledgeChunk identifier.

        Returns:
            The matching chunk, or None when it does not exist.
        """

        result = await self._session.execute(
            select(KnowledgeChunk).where(
                KnowledgeChunk.id == chunk_id,
            ),
        )

        return result.scalar_one_or_none()

    async def list_by_knowledge_source_id(
        self,
        *,
        knowledge_source_id: str,
    ) -> Sequence[KnowledgeChunk]:
        """
        Retrieve all chunks belonging to a knowledge base.

        Args:
            knowledge_source_id:
                Knowledge source identifier.

        Returns:
            Knowledge chunks ordered by creation time.
        """

        result = await self._session.execute(
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.knowledge_source_id == knowledge_source_id,
            )
            .order_by(
                KnowledgeChunk.created_at,
            ),
        )

        return result.scalars().all()

    async def create(
        self, *, chunk_id: str, text: str, chunk_metadata: dict, knowledge_source_id: str
    ) -> KnowledgeChunk:
        """
        Create a knowledge chunk.

        Args:
            chunk_id:
                Identifier of the chunk.

            knowledge_source_id:
                Knowledge source identifier.

            text:
                Extracted textual content.

            chunk_metadata:
                Metadata associated with the chunk.

        Returns:
            The newly created KnowledgeChunk entity.
        """

        chunk = KnowledgeChunk(
            id=chunk_id,
            knowledge_source_id=knowledge_source_id,
            text=text,
            chunk_metadata=chunk_metadata,
        )

        self._session.add(chunk)

        await self._session.flush()

        return chunk

    async def update(
        self,
        *,
        chunk: KnowledgeChunk,
        text: str,
        chunk_metadata: dict,
    ) -> KnowledgeChunk:
        """
        Update the textual content and metadata of a chunk.

        Args:
            chunk:
                Existing KnowledgeChunk entity.

            text:
                Updated textual content.

            chunk_metadata:
                Updated chunk metadata.

        Returns:
            Updated KnowledgeChunk entity.
        """

        chunk.text = text
        chunk.chunk_metadata = chunk_metadata

        await self._session.flush()

        return chunk

    async def delete_by_id(
        self,
        *,
        chunk_id: str,
    ) -> bool:
        """
        Delete a single document chunk.

        Associated embeddings are removed through the database
        foreign-key cascade.

        Args:
            chunk_id:
                KnowledgeChunk identifier.

        Returns:
            True when a chunk was deleted, otherwise False.
        """

        result = await self._session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.id == chunk_id,
            ),
        )

        await self._session.flush()

        return bool(result.rowcount)

    async def delete_by_knowledge_source_id(
        self,
        *,
        knowledge_source_id: str,
    ) -> int:
        """
        Delete all chunks belonging to a knowledge source.

        Associated embeddings are removed through the database
        foreign-key cascade.

        Args:
            knowledge_source_id:
                Knowledge source identifier.

        Returns:
            Number of deleted chunks.
        """

        result = await self._session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.knowledge_source_id == knowledge_source_id,
            ),
        )

        await self._session.flush()

        return result.rowcount or 0
