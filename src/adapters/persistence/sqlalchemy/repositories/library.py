"""
Library repository.

Provides persistence operations for user/API-uploaded files.

Library represents transactional user-provided documents.
It is intentionally separate from the persistent legal knowledge
and RAG corpus.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.library import Library


class LibraryRepository:
    """
    Repository for user-uploaded file persistence.

    This repository owns file metadata only.

    It does not own:
        - document parsing
        - text extraction
        - chunking
        - embeddings
        - vector search
        - RAG
        - context construction
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create(
        self,
        library: Library,
    ) -> Library:
        """
        Persist a user-uploaded file.
        """

        self._session.add(library)

        await self._session.flush()

        await self._session.refresh(library)

        return library

    async def get_by_id(
        self,
        *,
        library_id: str,
    ) -> Library | None:
        """
        Retrieve an uploaded file by identifier.
        """

        return await self._session.get(
            Library,
            library_id,
        )

    async def list_by_conversation(
        self,
        *,
        conversation_id: str,
    ) -> list[Library]:
        """
        Retrieve all uploaded files belonging to a conversation.
        """

        result = await self._session.scalars(
            select(Library)
            .where(
                Library.conversation_id == conversation_id,
            )
            .order_by(
                Library.created_at.asc(),
            ),
        )

        return list(result)

    async def update(
        self,
        library: Library,
    ) -> Library:
        """
        Persist changes to an uploaded file.
        """

        await self._session.flush()

        await self._session.refresh(library)

        return library

    async def delete(
        self,
        library: Library,
    ) -> None:
        """
        Delete an uploaded file.
        """

        await self._session.delete(library)

        await self._session.flush()

    async def search(
        self,
        *,
        query: str | None = None,
        limit: int = 10,
    ) -> list[Library]:
        """
        Search uploaded files by persisted file metadata.

        This is metadata search only. It is not semantic or
        vector-based document retrieval.
        """

        if limit <= 0:
            return []

        statement = select(Library)

        if query and query.strip():
            pattern = f"%{query.strip()}%"

            statement = statement.where(
                or_(
                    Library.original_filename.ilike(pattern),
                    Library.filename.ilike(pattern),
                    Library.source_url.ilike(pattern),
                    Library.storage_path.ilike(pattern),
                ),
            )

        result = await self._session.scalars(
            statement.order_by(
                Library.created_at.asc(),
            ).limit(limit),
        )

        return list(result)
