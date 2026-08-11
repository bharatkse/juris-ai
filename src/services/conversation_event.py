"""
Conversation event service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import MessageRoleEnum
from src.core.exceptions.database import DatabaseError
from src.core.logger import get_logger
from src.db.models.conversation_event import ConversationEvent
from src.repositories.conversation_event import ConversationEventRepository
from src.services.base import BaseService

if TYPE_CHECKING:
    from src.core.types import ConversationEventId, ConversationId

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
        conversation_id: ConversationId,
        request_id: UUID,
        role: MessageRoleEnum,
        content: str,
        parent_event_id: ConversationEventId | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        """
        Create and persist a conversation event.

        Transaction ownership remains with the calling service.
        """

        event = ConversationEvent(
            conversation_id=conversation_id,
            request_id=request_id,
            parent_event_id=parent_event_id,
            role=role,
            content=content,
            event_metadata=metadata or {},
        )

        try:
            event = await self._repository.create(
                event,
            )

            logger.info(
                "Conversation event created.",
                extra={
                    "operation": "create_conversation_event",
                    "conversation_id": str(conversation_id),
                    "event_id": str(event.id),
                    "request_id": str(request_id),
                    "role": role.value,
                },
            )

            return event

        except SQLAlchemyError as exc:
            logger.exception(
                "Database error while creating conversation event.",
                extra={
                    "operation": "create_conversation_event",
                    "conversation_id": str(conversation_id),
                    "request_id": str(request_id),
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
