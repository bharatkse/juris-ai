"""
Conversation repository.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import exists, select

from src.db.models.conversation import Conversation
from src.repositories.base import BaseRepository


class ConversationRepository(BaseRepository):
    """
    Repository responsible for Conversation persistence.
    """

    _model = Conversation

    async def create(self, conversation: Conversation) -> Conversation:
        self._session.add(conversation)

        await self.flush()
        await self.refresh(conversation)

        return conversation

    async def get(
        self,
        conversation_id: UUID,
    ) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.deleted_at.is_(None),
        )

        result = await self._session.execute(statement)

        return cast(Conversation | None, result.scalar_one_or_none())

    async def exists(
        self,
        conversation_id: UUID,
    ) -> bool:
        statement = select(
            exists().where(
                Conversation.id == conversation_id,
                Conversation.deleted_at.is_(None),
            )
        )

        return bool(await self._session.scalar(statement))

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(
                Conversation.deleted_at.is_(None),
            )
            .order_by(
                Conversation.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def archive(
        self,
        conversation: Conversation,
    ) -> None:
        conversation.archive()

        await self.flush()
