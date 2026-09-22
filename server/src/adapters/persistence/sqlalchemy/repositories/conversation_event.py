"""
Conversation event repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from adapters.persistence.sqlalchemy.models.conversation_event import ConversationEvent
from adapters.persistence.sqlalchemy.repositories.base import BaseRepository

if TYPE_CHECKING:
    from datetime import datetime

    from core.enums import MessageRoleEnum
    from core.types import ConversationEventId, ConversationId


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

    async def get_by_id(
        self,
        *,
        event_id: ConversationEventId,
    ) -> ConversationEvent | None:
        """
        Retrieve a conversation event by ID alone.

        Used where only the event ID is known up front (e.g. resuming
        a paused agent action, which carries conversation_event_id but
        not conversation_id) -- get() above is preferred whenever the
        conversation_id is already known, since it also scopes the
        lookup to that conversation.
        """

        statement = self.select().where(
            self._model.id == event_id,
        )

        result = await self._session.execute(
            statement,
        )

        return result.scalar_one_or_none()

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

    async def list_by_role_since(
        self,
        *,
        conversation_id: ConversationId,
        role: MessageRoleEnum,
        after: datetime | None,
        limit: int,
    ) -> list[ConversationEvent]:
        """
        Events of one role created strictly after ``after`` (all of them
        when None), oldest first, at most ``limit``.

        Used by user-memory extraction, which must only ever read USER
        messages -- never assistant, tool or system content.
        """

        statement = self.select().where(
            self._model.conversation_id == conversation_id,
            self._model.role == role,
        )

        if after is not None:
            statement = statement.where(
                self._model.created_at > after,
            )

        result = await self._session.execute(
            statement.order_by(
                self._model.created_at.asc(),
            ).limit(
                limit,
            ),
        )

        return list(
            result.scalars().all(),
        )

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
