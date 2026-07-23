"""
Conversation event repository.
"""

from __future__ import annotations

from sqlalchemy import select

from src.core.enums import MessageRole
from src.db.models.conversation_event import ConversationEvent
from src.repositories.base import BaseRepository


class ConversationEventRepository(BaseRepository):
    """
    Repository responsible for ConversationEvent persistence.
    """

    async def create(
        self,
        *,
        conversation_id: str,
        role: MessageRole,
        content: str,
        parent_event_id: str | None = None,
        metadata: dict | None = None,
    ) -> ConversationEvent:
        """
        Create a conversation event.
        """

        event = ConversationEvent(
            conversation_id=conversation_id,
            parent_event_id=parent_event_id,
            role=role,
            content=content,
            event_metadata=metadata,
        )

        self._session.add(event)

        await self.flush()
        await self.refresh(event)

        return event

    async def get(
        self,
        event_id: str,
    ) -> ConversationEvent | None:
        """
        Retrieve an event by identifier.
        """

        statement = select(ConversationEvent).where(
            ConversationEvent.id == event_id,
        )

        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_conversation(
        self,
        conversation_id: str,
    ) -> list[ConversationEvent]:
        """
        Retrieve all events for a conversation.
        """

        statement = (
            select(ConversationEvent)
            .where(
                ConversationEvent.conversation_id == conversation_id,
            )
            .order_by(
                ConversationEvent.created_at.asc(),
            )
        )

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def get_recent_events(
        self,
        *,
        conversation_id: str,
        limit: int = 20,
    ) -> list[ConversationEvent]:
        """
        Retrieve the most recent events for a conversation.

        Events are returned in chronological order.
        """

        statement = (
            select(ConversationEvent)
            .where(
                ConversationEvent.conversation_id == conversation_id,
            )
            .order_by(
                ConversationEvent.created_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(statement)

        events = list(result.scalars().all())

        events.reverse()

        return events
