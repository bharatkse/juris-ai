"""
Conversation service.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import DEFAULT_CONVERSATION_TITLE
from src.core.exceptions.httpx import UserNotFoundError
from src.core.types import ConversationId
from src.db.models.conversation import Conversation
from src.repositories.conversation import ConversationRepository
from src.repositories.user import UserRepository
from src.schemas.conversation import CreateConversationRequest
from src.services.base import BaseService


class ConversationService(BaseService):
    """
    Business logic for conversations.
    """

    def __init__(
        self,
        session: AsyncSession,
        repository: ConversationRepository,
        user_repository: UserRepository,
    ) -> None:
        super().__init__(session)

        self._repository = repository
        self._user_repository = user_repository

    async def create(self, request: CreateConversationRequest) -> Conversation:
        """
        Create a new conversation.
        """
        user = await self._user_repository.get(request.user_id)

        if user is None:
            raise UserNotFoundError("User not found.")

        try:
            conversation = await self._repository.create(
                Conversation(
                    title=request.title or DEFAULT_CONVERSATION_TITLE,
                    user_id=request.user_id,
                ),
            )

            await self.commit()

            return conversation

        except Exception:
            await self.rollback()
            raise

    async def get(
        self,
        conversation_id: ConversationId,
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

        except Exception:
            await self.rollback()
            raise
