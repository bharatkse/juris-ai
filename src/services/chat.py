"""
Chat service.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.db.models.conversation import Conversation as ConversationModel

from src.core.dto.agent import AgentResponseDTO
from src.core.enums import MessageRoleEnum
from src.core.logger import get_logger
from src.core.schemas.conversation import ConversationMessageSchema
from src.core.types import ConversationEventId, ConversationId, UserId
from src.orchestration.orchestrator import AIOrchestrator
from src.orchestration.schemas.request import OrchestratorRequest
from src.services.base import BaseService
from src.services.conversation import ConversationService
from src.services.conversation_event import ConversationEventService
from src.services.dto.chat import ChatResultDTO
from src.services.dto.stream import ChatStreamChunkDTO

logger = get_logger(__name__)


class ChatService(BaseService):
    """
    Coordinates chat interactions and owns the database transaction.
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
        request_id: UUID,
    ) -> ChatResultDTO:
        """
        Process a chat request.

        ChatService owns the transaction boundary:

        1. Create the user event.
        2. Execute orchestration.
        3. Create the assistant event.
        4. Commit the transaction.

        Any failure rolls back the entire transaction.
        """

        logger.info(
            "Processing chat request.",
            extra={
                "operation": "chat",
                "request_id": str(request_id),
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
                request_id=request_id,
                role=MessageRoleEnum.USER,
                content=message,
            )

            orchestration_request = await self._build_chat_request(
                conversation=conversation,
                current_event_id=user_event.id,
                message=message,
                request_id=request_id,
            )

            response = await self._orchestrator.handle(
                request=orchestration_request,
            )

            assistant_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                request_id=request_id,
                parent_event_id=user_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=response.content,
                metadata=response.metadata.model_dump(
                    mode="json",
                ),
            )

            # ChatService owns the transaction.
            await self.commit()

            logger.info(
                "Chat request completed.",
                extra={
                    "operation": "chat",
                    "request_id": str(request_id),
                    "conversation_id": str(conversation.id),
                    "user_id": str(user_id),
                    "user_event_id": str(user_event.id),
                    "assistant_event_id": str(assistant_event.id),
                },
            )

            return ChatResultDTO(
                conversation=conversation,
                user_event=user_event,
                assistant_event=assistant_event,
                response=response,
            )

        except Exception:
            await self.rollback()

            logger.exception(
                "Chat request failed.",
                extra={
                    "operation": "chat",
                    "request_id": str(request_id),
                    "conversation_id": str(conversation_id),
                    "user_id": str(user_id),
                },
            )

            raise

    async def stream_chat(
        self,
        *,
        user_id: UserId,
        conversation_id: ConversationId,
        message: str,
        request_id: UUID,
    ) -> AsyncIterator[ChatStreamChunkDTO]:
        """
        Stream a chat response.

        The transaction remains open until the final assistant
        event is persisted successfully.
        """

        logger.info(
            "Starting chat stream.",
            extra={
                "operation": "stream_chat",
                "request_id": str(request_id),
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
                request_id=request_id,
                role=MessageRoleEnum.USER,
                content=message,
            )

            orchestration_request = await self._build_chat_request(
                conversation=conversation,
                current_event_id=user_event.id,
                message=message,
                request_id=request_id,
            )

            stream = self._orchestrator.stream(
                request=orchestration_request,
            )

            final_response: AgentResponseDTO | None = None

            async for chunk in stream:
                if chunk.is_complete:
                    final_response = chunk.response

                yield chunk

            if final_response is None:
                raise RuntimeError(
                    "Streaming completed without a final response.",
                )

            assistant_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                request_id=request_id,
                parent_event_id=user_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=final_response.content,
                metadata=final_response.metadata.model_dump(
                    mode="json",
                ),
            )

            # Commit only after the complete response has been
            # successfully persisted.
            await self.commit()

            logger.info(
                "Chat stream completed.",
                extra={
                    "operation": "stream_chat",
                    "request_id": str(request_id),
                    "conversation_id": str(conversation.id),
                    "user_id": str(user_id),
                    "user_event_id": str(user_event.id),
                    "assistant_event_id": str(assistant_event.id),
                },
            )

        except Exception:
            await self.rollback()

            logger.exception(
                "Chat stream failed.",
                extra={
                    "operation": "stream_chat",
                    "request_id": str(request_id),
                    "conversation_id": str(conversation_id),
                    "user_id": str(user_id),
                },
            )

            raise

    async def _build_chat_request(
        self,
        *,
        conversation: ConversationModel,
        current_event_id: ConversationEventId,
        message: str,
        request_id: UUID,
    ) -> OrchestratorRequest:
        """
        Build the orchestration request from conversation history.
        """

        events = await self._conversation_event_service.list(
            conversation_id=conversation.id,
        )

        history = [
            ConversationMessageSchema(
                content=event.content,
                role=event.role,
            )
            for event in events
            if event.id != current_event_id
        ]

        return OrchestratorRequest(
            request_id=request_id,
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            message=message,
            history=history,
        )
