"""
Conversation event repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from src.db.models.conversation_event import ConversationEvent
from src.repositories.base import BaseRepository

if TYPE_CHECKING:
    from src.core.types import ConversationEventId, ConversationId


class ConversationEventRepository(
    BaseRepository[ConversationEvent],
):
    """
    Repository responsible for ConversationEvent persistence.
    """

    _model = ConversationEvent

    async def create(
        self,
        event: ConversationEvent,
    ) -> ConversationEvent:
        """
        Persist a conversation event.
        """

        return await self.persist(
            event,
        )

    async def get(
        self,
        *,
        conversation_id: ConversationId,
        event_id: ConversationEventId,
    ) -> ConversationEvent | None:
        """
        Retrieve a conversation event.
        """

        statement = self.select().where(
            self._model.id == event_id,
            self._model.conversation_id == conversation_id,
        )

        result = await self._session.execute(
            statement,
        )

        return cast(
            ConversationEvent | None,
            result.scalar_one_or_none(),
        )

    async def list(
        self,
        *,
        conversation_id: ConversationId,
        limit: int | None = None,
    ) -> list[ConversationEvent]:
        """
        Retrieve conversation events.

        Events are always returned in chronological order.
        """

        statement = self.select().where(
            self._model.conversation_id == conversation_id,
        )

        if limit is None:
            statement = statement.order_by(
                self._model.created_at.asc(),
            )

        else:
            statement = statement.order_by(
                self._model.created_at.desc(),
            ).limit(
                limit,
            )

        result = await self._session.execute(
            statement,
        )

        events = list(
            result.scalars().all(),
        )

        if limit is not None:
            events.reverse()

        return events

    async def update(
        self,
        event: ConversationEvent,
    ) -> ConversationEvent:
        """
        Persist updates to a conversation event.
        """

        await self.flush()

        await self.refresh(
            event,
        )

        return event
