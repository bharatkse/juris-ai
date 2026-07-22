"""
Conversation service.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import DEFAULT_CONVERSATION_TITLE
from src.db.models.conversation import Conversation
from src.repositories.conversation import ConversationRepository
from src.services.base import BaseService


class ConversationService(BaseService):
    """
    Business logic for conversations.
    """

    def __init__(
        self,
        session: AsyncSession,
        repository: ConversationRepository,
    ) -> None:
        super().__init__(session)

        self._repository = repository

    async def create(self) -> Conversation:
        """
        Create a new conversation.
        """

        try:
            conversation = await self._repository.create(
                title=DEFAULT_CONVERSATION_TITLE,
            )

            await self.commit()

            return conversation

        except BaseException:
            await self.rollback()
            raise

    async def get(
        self,
        conversation_id: UUID,
    ) -> Conversation | None:
        """
        Retrieve a conversation.
        """

        return await self._repository.get(
            conversation_id,
        )

    async def archive(
        self,
        conversation: Conversation,
    ) -> None:
        """
        Archive a conversation.
        """

        try:
            await self._repository.archive(
                conversation,
            )

            await self.commit()

        except BaseException:
            await self.rollback()
            raise
