"""
Document chunk repository.

Provides persistence operations for textual document chunks.

A DocumentChunk represents extracted textual content belonging to a
source document. Embedding representations are persisted separately
through DocumentChunkEmbeddingRepository.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.document_chunk import (
    DocumentChunk,
)


class DocumentChunkRepository:
    """
    Repository for persisted document chunks.

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
    ) -> DocumentChunk | None:
        """
        Retrieve a document chunk by identifier.

        Args:
            chunk_id:
                DocumentChunk identifier.

        Returns:
            The matching chunk, or None when it does not exist.
        """

        result = await self._session.execute(
            select(DocumentChunk).where(
                DocumentChunk.id == chunk_id,
            ),
        )

        return result.scalar_one_or_none()

    async def list_by_document_id(
        self,
        *,
        document_id: str,
    ) -> Sequence[DocumentChunk]:
        """
        Retrieve all chunks belonging to a document.

        Args:
            document_id:
                Source document identifier.

        Returns:
            Document chunks ordered by creation time.
        """

        result = await self._session.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
            )
            .order_by(
                DocumentChunk.created_at,
            ),
        )

        return result.scalars().all()

    async def create(
        self,
        *,
        chunk_id: str,
        text: str,
        chunk_metadata: dict,
        document_id: str | None,
    ) -> DocumentChunk:
        """
        Create a document chunk.

        Args:
            chunk_id:
                Identifier of the chunk.

            document_id:
                Source document identifier.

            text:
                Extracted textual content.

            chunk_metadata:
                Metadata associated with the chunk.

        Returns:
            The newly created DocumentChunk entity.
        """

        chunk = DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            text=text,
            chunk_metadata=chunk_metadata,
        )

        self._session.add(chunk)

        await self._session.flush()

        return chunk

    async def update(
        self,
        *,
        chunk: DocumentChunk,
        text: str,
        chunk_metadata: dict,
    ) -> DocumentChunk:
        """
        Update the textual content and metadata of a chunk.

        Args:
            chunk:
                Existing DocumentChunk entity.

            text:
                Updated textual content.

            chunk_metadata:
                Updated chunk metadata.

        Returns:
            Updated DocumentChunk entity.
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
                DocumentChunk identifier.

        Returns:
            True when a chunk was deleted, otherwise False.
        """

        result = await self._session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.id == chunk_id,
            ),
        )

        await self._session.flush()

        return bool(result.rowcount)

    async def delete_by_document_id(
        self,
        *,
        document_id: str,
    ) -> int:
        """
        Delete all chunks belonging to a document.

        Associated embeddings are removed through the database
        foreign-key cascade.

        Args:
            document_id:
                Source document identifier.

        Returns:
            Number of deleted chunks.
        """

        result = await self._session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
            ),
        )

        await self._session.flush()

        return result.rowcount or 0
