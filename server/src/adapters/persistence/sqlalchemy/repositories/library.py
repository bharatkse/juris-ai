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

from adapters.persistence.sqlalchemy.models.conversation import Conversation
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

    async def list_owned_ids(
        self,
        *,
        user_id: str,
    ) -> set[str]:
        """
        Resolve every Library id owned (transitively, via
        Conversation.user_id) by user_id.

        The enforcement point for real per-user Library ownership --
        called by AuthorizationService.get_allowed_library_ids(), the
        one thing that decides what set[str] gets bound onto
        RequestContext.allowed_library_ids for the rest of the
        request. Library has no direct user_id column; conversation_id
        -> Conversation.user_id is the only real ownership chain that
        exists today (see Library's model docstring) -- no new tenant
        table, this is a straight join over what already exists.
        """

        statement = (
            select(Library.id)
            .join(
                Conversation,
                Library.conversation_id == Conversation.id,
            )
            .where(
                Conversation.user_id == user_id,
            )
        )

        result = await self._session.scalars(statement)

        return set(result)

    async def list_by_conversation(
        self,
        *,
        conversation_id: str,
        allowed_library_ids: set[str] | None = None,
    ) -> list[Library]:
        """
        Retrieve all uploaded files belonging to a conversation.

        allowed_library_ids, when not None, restricts the result to
        that set at the SQL level (not a post-filter) -- see
        AuthorizationService.get_allowed_library_ids(). An empty set
        short-circuits to [] without a query: "restricted to nothing"
        and "restricted to an empty IN (...)" mean the same thing, but
        some SQL dialects handle an empty IN(...) awkwardly, so this
        avoids relying on that.
        """

        if allowed_library_ids is not None and not allowed_library_ids:
            return []

        statement = select(Library).where(
            Library.conversation_id == conversation_id,
        )

        if allowed_library_ids is not None:
            statement = statement.where(Library.id.in_(allowed_library_ids))

        result = await self._session.scalars(
            statement.order_by(
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
        allowed_library_ids: set[str] | None = None,
    ) -> list[Library]:
        """
        Search uploaded files by persisted file metadata.

        This is metadata search only. It is not semantic or
        vector-based document retrieval.

        allowed_library_ids, when not None, restricts the result to
        that set at the SQL level (not a post-filter) -- see
        AuthorizationService.get_allowed_library_ids(). Previously this
        method had no owner-scoping parameter at all and scanned every
        Library row in the database, relying entirely on a caller-side
        Python filter after the fact (LibraryLookupTool's own
        allowed_library_ids check, kept as defense-in-depth on top of
        this, not instead of it).
        """

        if limit <= 0:
            return []

        if allowed_library_ids is not None and not allowed_library_ids:
            return []

        statement = select(Library)

        if allowed_library_ids is not None:
            statement = statement.where(Library.id.in_(allowed_library_ids))

        if query and query.strip():
            pattern = f"%{query.strip()}%"

            # Library.source_url does not exist on this model (Library
            # represents an upload boundary, not a fetched-by-URL
            # source -- that concept belongs to KnowledgeSource) --
            # matching it here was always an AttributeError waiting to
            # fire the moment a query was actually supplied.
            statement = statement.where(
                or_(
                    Library.original_filename.ilike(pattern),
                    Library.filename.ilike(pattern),
                    Library.storage_path.ilike(pattern),
                ),
            )

        result = await self._session.scalars(
            statement.order_by(
                Library.created_at.asc(),
            ).limit(limit),
        )

        return list(result)
