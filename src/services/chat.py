"""
Chat service.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import MessageRole
from src.core.logger import get_logger
from src.core.types import ConversationId, UserId
from src.orchestration.orchestrator import AIOrchestrator
from src.orchestration.request import OrchestratorRequest
from src.orchestration.response import AgentResponse
from src.services.base import BaseService
from src.services.conversation import ConversationService
from src.services.conversation_event import ConversationEventService
from src.services.models.chat import ChatResult
from src.services.models.stream import ChatStreamChunk

logger = get_logger(__name__)


class ChatService(BaseService):
    """
    Coordinates chat interactions.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        conversation_service: ConversationService,
        conversation_event_service: ConversationEventService,
        orchestrator: AIOrchestrator,
    ) -> None:
        super().__init__(
            session=session,
        )

        self._conversation_service = conversation_service
        self._conversation_event_service = conversation_event_service
        self._orchestrator = orchestrator

    async def chat(
        self,
        *,
        user_id: UserId,
        conversation_id: ConversationId,
        message: str,
    ) -> ChatResult:
        """
        Process a chat request.
        """

        logger.info(
            "Processing chat request.",
            extra={
                "operation": "chat",
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
            },
        )

        conversation = await self._conversation_service.get_or_raise(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        try:
            user_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=message,
            )

            request = await self._build_chat_request(
                conversation=conversation,
                message=message,
            )

            response = await self._orchestrator.handle(
                request=request,
            )

            assistant_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                parent_event_id=user_event.id,
                role=MessageRole.ASSISTANT,
                content=response.content,
                metadata=response.metadata,
            )

            await self.commit()

            logger.info(
                "Chat request completed.",
                extra={
                    "operation": "chat",
                    "conversation_id": str(conversation.id),
                    "user_id": str(user_id),
                },
            )

            return ChatResult(
                conversation=conversation,
                user_event=user_event,
                assistant_event=assistant_event,
                response=response,
            )

        except SQLAlchemyError:
            await self.rollback()
            raise

    async def stream_chat(
        self,
        *,
        user_id: UserId,
        conversation_id: ConversationId,
        message: str,
    ) -> AsyncIterator[ChatStreamChunk]:
        """
        Stream a chat response.
        """

        conversation = await self._conversation_service.get_or_raise(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        try:
            user_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=message,
            )

            request = await self._build_chat_request(
                conversation=conversation,
                message=message,
            )

            stream = self._orchestrator.stream(
                request=request,
            )

            response: AgentResponse | None = None

            async for chunk in stream:
                if chunk.is_complete:
                    response = chunk.response

                yield chunk

            if response is None:
                raise RuntimeError(
                    "Streaming completed without a final response.",
                )

            await self._conversation_event_service.create(
                conversation_id=conversation.id,
                parent_event_id=user_event.id,
                role=MessageRole.ASSISTANT,
                content=response.content,
                metadata=response.metadata,
            )

            await self.commit()

        except SQLAlchemyError:
            await self.rollback()
            raise

    async def _build_chat_request(
        self,
        *,
        conversation,
        message: str,
    ) -> OrchestratorRequest:
        """
        Build the orchestration request.
        """

        history = await self._conversation_event_service.list(
            conversation_id=conversation.id,
        )

        #
        # TODO
        #
        # User profile
        # Uploaded files
        # Runtime context
        #

        return OrchestratorRequest(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            message=message,
            history=history,
        )
