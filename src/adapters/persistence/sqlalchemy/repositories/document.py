"""
Document repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.document import Document


class DocumentRepository:
    """
    Repository for document persistence.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create(
        self,
        document: Document,
    ) -> Document:
        """
        Persist a document.
        """

        self._session.add(
            document,
        )

        await self._session.flush()

        await self._session.refresh(
            document,
        )

        return document

    async def get_by_id(
        self,
        *,
        document_id: str,
    ) -> Document | None:
        """
        Retrieve a document by identifier.
        """

        return await self._session.get(
            Document,
            document_id,
        )

    async def list_by_conversation(
        self,
        *,
        conversation_id: str,
    ) -> list[Document]:
        """
        Retrieve all documents for a conversation.
        """

        result = await self._session.scalars(
            select(
                Document,
            )
            .where(
                Document.conversation_id == conversation_id,
            )
            .order_by(
                Document.created_at.asc(),
            ),
        )

        return list(
            result,
        )

    async def update(
        self,
        document: Document,
    ) -> Document:
        """
        Persist document changes.
        """

        await self._session.flush()

        await self._session.refresh(
            document,
        )

        return document

    async def delete(
        self,
        document: Document,
    ) -> None:
        """
        Delete a document.
        """

        await self._session.delete(
            document,
        )
        await self._session.flush()

    async def search(self, query, limit):
        pass
