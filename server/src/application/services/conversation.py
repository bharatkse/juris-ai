"""
Conversation service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.models.conversation import Conversation
from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from application.services.base import BaseService
from core.constants import DEFAULT_CONVERSATION_TITLE
from core.exceptions.database import DatabaseError
from core.exceptions.httpx import ConversationInactiveError
from core.exceptions.httpx import NotFoundError as ConversationNotFoundError
from core.utils.datetime import utcnow

if TYPE_CHECKING:
    from api.schemas.conversation import CreateConversationRequest
    from core.types import ConversationId, UserId

logger = get_logger(__name__)


class ConversationService(BaseService):
    """
    Business logic for conversation management.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: ConversationRepository,
    ) -> None:
        super().__init__(session)
        self._repository = repository

    async def create(
        self,
        *,
        user_id: UserId,
        request: CreateConversationRequest,
    ) -> Conversation:
        """
        Create a new conversation.
        """

        conversation = Conversation(
            title=request.title or DEFAULT_CONVERSATION_TITLE,
            user_id=user_id,
        )

        try:
            conversation = await self._repository.create(
                conversation,
            )

            await self.commit()

            logger.info(
                "Conversation created.",
                extra={
                    "operation": "create_conversation",
                    "conversation_id": str(conversation.id),
                    "user_id": str(conversation.user_id),
                },
            )

            return conversation

        except IntegrityError as exc:
            await self.rollback()

            logger.exception(
                "Failed to create conversation due to integrity constraint.",
                extra={
                    "operation": "create_conversation",
                    "user_id": user_id,
                },
            )

            raise DatabaseError(
                "Failed to create conversation.",
            ) from exc

        except SQLAlchemyError as exc:
            await self.rollback()

            logger.exception(
                "Database error while creating conversation.",
                extra={
                    "operation": "create_conversation",
                    "user_id": user_id,
                },
            )

            raise DatabaseError(
                "Failed to create conversation.",
            ) from exc

    async def get(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
    ) -> Conversation | None:
        """
        Retrieve a conversation.
        """

        return await self._repository.get(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def get_or_raise(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
    ) -> Conversation:
        """
        Retrieve an active conversation.

        Raises:
            ConversationNotFoundError
            ConversationInactiveError
        """

        conversation = await self.get(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if conversation is None:
            logger.warning(
                "Conversation not found.",
                extra={
                    "operation": "get_conversation",
                    "conversation_id": str(conversation_id),
                    "user_id": str(user_id),
                },
            )

            raise ConversationNotFoundError(
                message="Conversation not found.",
            )

        if not conversation.is_active:
            logger.warning(
                "Conversation is inactive.",
                extra={
                    "operation": "get_conversation",
                    "conversation_id": str(conversation.id),
                    "user_id": str(user_id),
                },
            )

            raise ConversationInactiveError(
                "Conversation is inactive.",
            )

        return conversation

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

        return await self._repository.list(
            user_id=user_id,
            offset=offset,
            limit=limit,
        )

    async def archive(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
    ) -> Conversation:
        """
        Archive a conversation.
        """

        conversation = await self.get_or_raise(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        conversation.archive()

        try:
            conversation = await self._repository.update(
                conversation,
            )

            await self.commit()

            logger.info(
                "Conversation archived.",
                extra={
                    "operation": "archive_conversation",
                    "conversation_id": str(conversation.id),
                    "user_id": str(user_id),
                },
            )

            return conversation

        except SQLAlchemyError as exc:
            await self.rollback()

            logger.exception(
                "Database error while archiving conversation.",
                extra={
                    "operation": "archive_conversation",
                    "conversation_id": str(conversation_id),
                    "user_id": str(user_id),
                },
            )

            raise DatabaseError(
                "Failed to archive conversation.",
            ) from exc

    async def set_memory_disabled(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
        disabled: bool,
    ) -> Conversation:
        """
        Turn the per-conversation "don't remember this" switch on or off.

        Forward-only. Turning it on stops anything said in this
        conversation from now on being saved to the user's long-term
        memory. It does NOT delete facts already saved from earlier
        messages in this conversation (or from any other), and it does
        not touch the conversation's history. Removing what is already
        stored is done from the user's memory list, one item at a time,
        or by turning memory off altogether, which deletes everything.

        Turning it back OFF (allowing memory again) moves the extraction
        watermark to now, so nothing said while it was on is ever read
        later: the switch is a promise about those messages, not a pause.

        Raises:
            ConversationNotFoundError
            ConversationInactiveError
        """

        conversation = await self.get_or_raise(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if conversation.memory_disabled == disabled:
            return conversation

        conversation.memory_disabled = disabled

        if not disabled:
            conversation.memory_extracted_through_created_at = utcnow()

        try:
            conversation = await self._repository.update(
                conversation,
            )

            await self.commit()

            logger.info(
                "Conversation memory switch changed.",
                extra={
                    "operation": "set_conversation_memory_disabled",
                    "conversation_id": str(conversation.id),
                    "user_id": str(user_id),
                    "memory_disabled": disabled,
                },
            )

            return conversation

        except SQLAlchemyError as exc:
            await self.rollback()

            logger.exception(
                "Database error while changing conversation memory switch.",
                extra={
                    "operation": "set_conversation_memory_disabled",
                    "conversation_id": str(conversation_id),
                    "user_id": str(user_id),
                },
            )

            raise DatabaseError(
                "Failed to update conversation memory setting.",
            ) from exc
