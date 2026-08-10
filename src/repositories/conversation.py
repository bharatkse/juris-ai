"""
Conversation repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import exists, func, select

from src.db.models.conversation import Conversation
from src.repositories.base import BaseRepository

if TYPE_CHECKING:
    from src.core.types import ConversationId, UserId


class ConversationRepository(
    BaseRepository[Conversation],
):
    """
    Repository responsible for Conversation persistence.
    """

    _model = Conversation

    async def create(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """
        Persist a new conversation.
        """

        return await self.persist(
            conversation,
        )

    async def get(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
    ) -> Conversation | None:
        """
        Retrieve a conversation.
        """

        statement = self.active_select().where(
            self._model.id == conversation_id,
            self._model.user_id == user_id,
        )

        result = await self._session.execute(
            statement,
        )

        return cast(
            Conversation | None,
            result.scalar_one_or_none(),
        )

    async def exists(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
    ) -> bool:
        """
        Check whether a conversation exists.
        """

        statement = self.select().with_only_columns(
            exists().where(
                self._model.id == conversation_id,
                self._model.user_id == user_id,
                self._model.deleted_at.is_(None),
            ),
        )

        return bool(
            await self._session.scalar(
                statement,
            ),
        )

    async def list(
        self,
        *,
        user_id: UserId,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Conversation], int]:
        """
        Retrieve paginated conversations for a user.
        """

        statement = (
            self.active_select()
            .where(
                self._model.user_id == user_id,
            )
            .order_by(
                self._model.updated_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(
            statement,
        )

        conversations = list(
            result.scalars().all(),
        )

        count_statement = (
            select(func.count())
            .select_from(self._model)
            .where(
                self._model.user_id == user_id,
                self._model.deleted_at.is_(None),
            )
        )

        total = await self._session.scalar(
            count_statement,
        )

        return conversations, total or 0

    async def update(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """
        Persist updates to a conversation.
        """

        await self.flush()

        await self.refresh(
            conversation,
        )

        return conversation
