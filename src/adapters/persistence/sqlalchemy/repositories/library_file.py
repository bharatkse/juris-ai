"""
Upload file repository.

Provides persistence operations for user/API-uploaded files.

LibraryFile represents transactional user-provided documents.
It is intentionally separate from the persistent legal knowledge
and RAG corpus.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.library_file import LibraryFile


class LibraryFileRepository:
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
        library_file: LibraryFile,
    ) -> LibraryFile:
        """
        Persist a user-uploaded file.
        """

        self._session.add(library_file)

        await self._session.flush()

        await self._session.refresh(library_file)

        return library_file

    async def get_by_id(
        self,
        *,
        library_file_id: str,
    ) -> LibraryFile | None:
        """
        Retrieve an uploaded file by identifier.
        """

        return await self._session.get(
            LibraryFile,
            library_file_id,
        )

    async def list_by_conversation(
        self,
        *,
        conversation_id: str,
    ) -> list[LibraryFile]:
        """
        Retrieve all uploaded files belonging to a conversation.
        """

        result = await self._session.scalars(
            select(LibraryFile)
            .where(
                LibraryFile.conversation_id == conversation_id,
            )
            .order_by(
                LibraryFile.created_at.asc(),
            ),
        )

        return list(result)

    async def update(
        self,
        library_file: LibraryFile,
    ) -> LibraryFile:
        """
        Persist changes to an uploaded file.
        """

        await self._session.flush()

        await self._session.refresh(library_file)

        return library_file

    async def delete(
        self,
        library_file: LibraryFile,
    ) -> None:
        """
        Delete an uploaded file.
        """

        await self._session.delete(library_file)

        await self._session.flush()

    async def search(
        self,
        *,
        query: str | None = None,
        limit: int = 10,
    ) -> list[LibraryFile]:
        """
        Search uploaded files by persisted file metadata.

        This is metadata search only. It is not semantic or
        vector-based document retrieval.
        """

        if limit <= 0:
            return []

        statement = select(LibraryFile)

        if query and query.strip():
            pattern = f"%{query.strip()}%"

            statement = statement.where(
                or_(
                    LibraryFile.original_filename.ilike(pattern),
                    LibraryFile.filename.ilike(pattern),
                    LibraryFile.source_url.ilike(pattern),
                    LibraryFile.storage_path.ilike(pattern),
                ),
            )

        result = await self._session.scalars(
            statement.order_by(
                LibraryFile.created_at.asc(),
            ).limit(limit),
        )

        return list(result)
