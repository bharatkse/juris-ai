"""
Conversation event service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import MessageRole
from src.core.exceptions.database import DatabaseError
from src.core.logger import get_logger
from src.db.models.conversation_event import ConversationEvent
from src.repositories.conversation_event import ConversationEventRepository
from src.services.base import BaseService

if TYPE_CHECKING:
    from src.core.types import ConversationId
    from src.db.models.conversation import Conversation

logger = get_logger(__name__)


class ConversationEventService(BaseService):
    """
    Business logic for conversation events.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: ConversationEventRepository,
    ) -> None:
        super().__init__(
            session=session,
        )

        self._repository = repository

    async def create(
        self,
        *,
        conversation: Conversation,
        role: MessageRole,
        content: str,
        parent_event: ConversationEvent | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        """
        Create a conversation event.
        """

        event = ConversationEvent(
            conversation_id=conversation.id,
            parent_event_id=(parent_event.id if parent_event else None),
            role=role,
            content=content,
            event_metadata=metadata or {},
        )

        try:
            event = await self._repository.create(
                event,
            )

            await self.commit()

            logger.info(
                "Conversation event created.",
                extra={
                    "operation": "create_conversation_event",
                    "conversation_id": str(conversation.id),
                    "event_id": str(event.id),
                    "role": role.value,
                },
            )

            return event

        except SQLAlchemyError as exc:
            await self.rollback()

            logger.exception(
                "Database error while creating conversation event.",
                extra={
                    "operation": "create_conversation_event",
                    "conversation_id": str(conversation.id),
                    "role": role.value,
                },
            )

            raise DatabaseError(
                "Failed to create conversation event.",
            ) from exc

    async def list(
        self,
        *,
        conversation_id: ConversationId,
        limit: int | None = 20,
    ) -> list[ConversationEvent]:
        """
        Retrieve conversation history.

        Events are returned in chronological order.
        """

        return await self._repository.list(
            conversation_id=conversation_id,
            limit=limit,
        )
