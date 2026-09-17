"""
Knowledge source repository.

Provides persistence operations for approved knowledge sources.

KnowledgeSource represents material that is eligible for the global
knowledge/RAG corpus. It is intentionally independent of user-uploaded
files.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.knowledge_sources import (
    KnowledgeSource,
)


class KnowledgeSourceRepository:
    """
    Repository for knowledge source persistence.

    This repository owns KnowledgeSource lifecycle only.

    It does not own:
        - document parsing
        - chunking
        - embeddings
        - vector search
        - RAG retrieval
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

    async def create(
        self,
        knowledge_source: KnowledgeSource,
    ) -> KnowledgeSource:
        """
        Persist a knowledge source.

        Args:
            knowledge_source:
                KnowledgeSource entity to persist.

        Returns:
            Persisted KnowledgeSource entity.
        """

        self._session.add(knowledge_source)

        await self._session.flush()

        await self._session.refresh(knowledge_source)

        return knowledge_source

    async def get_by_id(
        self,
        *,
        knowledge_source_id: str,
    ) -> KnowledgeSource | None:
        """
        Retrieve a knowledge source by identifier.

        Args:
            knowledge_source_id:
                KnowledgeSource identifier.

        Returns:
            Matching entity, or None when it does not exist.
        """

        return await self._session.get(
            KnowledgeSource,
            knowledge_source_id,
        )

    async def get_by_checksum(
        self,
        *,
        checksum: str,
    ) -> KnowledgeSource | None:
        """
        Retrieve a knowledge source by content checksum.

        Useful for preventing duplicate ingestion of the same source.
        """

        result = await self._session.execute(
            select(KnowledgeSource).where(
                KnowledgeSource.checksum == checksum,
            ),
        )

        return result.scalar_one_or_none()

    async def list_all(
        self,
    ) -> Sequence[KnowledgeSource]:
        """
        Retrieve all knowledge sources.

        Returns:
            Knowledge sources ordered by creation time.
        """

        result = await self._session.execute(
            select(KnowledgeSource).order_by(
                KnowledgeSource.created_at.asc(),
            ),
        )

        return result.scalars().all()

    async def list_by_source_type(
        self,
        *,
        source_type: str,
    ) -> Sequence[KnowledgeSource]:
        """
        Retrieve knowledge sources of a specific source type.
        """

        result = await self._session.execute(
            select(KnowledgeSource)
            .where(
                KnowledgeSource.source_type == source_type,
            )
            .order_by(
                KnowledgeSource.created_at.asc(),
            ),
        )

        return result.scalars().all()

    async def update(
        self,
        knowledge_source: KnowledgeSource,
    ) -> KnowledgeSource:
        """
        Persist changes to a knowledge source.

        Args:
            knowledge_source:
                Existing KnowledgeSource entity.

        Returns:
            Updated KnowledgeSource entity.
        """

        await self._session.flush()

        await self._session.refresh(
            knowledge_source,
        )

        return knowledge_source

    async def delete(
        self,
        knowledge_source: KnowledgeSource,
    ) -> None:
        """
        Delete a knowledge source.

        Related chunks and their embeddings are removed through the
        database/ORM cascade configuration.
        """

        await self._session.delete(
            knowledge_source,
        )

        await self._session.flush()

    async def search(
        self,
        *,
        query: str | None = None,
        limit: int = 10,
    ) -> list[KnowledgeSource]:
        """
        Search knowledge sources by persisted source metadata.

        This is metadata search only. It is not semantic or
        vector-based retrieval.
        """

        if limit <= 0:
            return []

        statement = select(KnowledgeSource)

        if query and query.strip():
            pattern = f"%{query.strip()}%"

            conditions = [
                KnowledgeSource.source_url.ilike(pattern),
                KnowledgeSource.original_filename.ilike(pattern),
                KnowledgeSource.filename.ilike(pattern),
                KnowledgeSource.storage_path.ilike(pattern),
            ]

            from sqlalchemy import or_

            statement = statement.where(
                or_(*conditions),
            )

        result = await self._session.scalars(
            statement.order_by(
                KnowledgeSource.created_at.asc(),
            ).limit(limit),
        )

        return list(result)
