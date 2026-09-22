"""
Conversation repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import CursorResult, exists, func, select, update

from adapters.persistence.sqlalchemy.models.conversation import Conversation
from adapters.persistence.sqlalchemy.repositories.base import BaseRepository

if TYPE_CHECKING:
    from datetime import datetime

    from core.types import ConversationId, UserId


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

    async def get_memory_disabled(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
    ) -> bool | None:
        """
        The conversation's "don't remember this" switch, or None when
        there is no such (non-archived) conversation for ``user_id``.

        A column select, not ``get()``: it reads the value from the
        database rather than from an ORM object the session may already
        hold, so a switch flipped moments ago is seen.
        """

        result = await self._session.execute(
            select(self._model.memory_disabled).where(
                self._model.id == conversation_id,
                self._model.user_id == user_id,
                self._model.deleted_at.is_(None),
            ),
        )

        return result.scalar_one_or_none()

    async def claim_memory_extraction(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
        expected_watermark: datetime | None,
        new_watermark: datetime,
    ) -> bool:
        """
        Atomically advance the memory-extraction watermark, but only if
        nothing has changed since it was read.

        One conditional UPDATE, so all of these hold or none do: the
        conversation belongs to ``user_id``, is not archived, still has
        "don't remember this" OFF (it may have been switched on while the
        LLM was running), and the watermark is still
        ``expected_watermark`` (another extraction did not get there
        first). Returns True when this caller now owns the batch.
        """

        watermark = self._model.memory_extracted_through_created_at

        result = await self._session.execute(
            update(self._model)
            .where(
                self._model.id == conversation_id,
                self._model.user_id == user_id,
                self._model.deleted_at.is_(None),
                self._model.memory_disabled.is_(False),
                watermark.is_(None)
                if expected_watermark is None
                else watermark == expected_watermark,
            )
            .values(memory_extracted_through_created_at=new_watermark)
            .execution_options(synchronize_session=False),
        )

        return cast(CursorResult[Any], result).rowcount == 1
