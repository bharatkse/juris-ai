"""
Chat service.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dto.agent import AgentResponseDTO
from src.core.enums import MessageRoleEnum
from src.core.logger import get_logger
from src.core.schemas.conversation import ConversationMessageSchema
from src.core.types import ConversationEventId, ConversationId, UserId
from src.orchestration.schemas.request import OrchestratorRequest
from src.services.base import BaseService
from src.services.internal_dto.chat import ChatResultDTO
from src.services.internal_dto.stream import ChatStreamChunkDTO

if TYPE_CHECKING:
    from src.core.dto.tool import ToolFileDTO
    from src.db.models.conversation import Conversation as ConversationModel
    from src.orchestration.orchestrator import AIOrchestrator
    from src.services.action_workflow import ActionWorkflowService
    from src.services.conversation import ConversationService
    from src.services.conversation_event import ConversationEventService

logger = get_logger(__name__)


class ChatService(BaseService):
    """
    Coordinates chat interactions.

    Responsibilities:
    - Persist conversation events.
    - Build the orchestration request.
    - Delegate reasoning, planning, execution, and action workflow
      to AIOrchestrator.
    - Return approval-required responses without blocking.

    ChatService does not:
    - perform planning,
    - execute agents,
    - authorize actions directly,
    - evaluate approval policy,
    - prepare actions directly,
    - execute concrete actions,
    - wait for human approval.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        conversation_service: ConversationService,
        conversation_event_service: ConversationEventService,
        orchestrator: AIOrchestrator,
        action_workflow_service: ActionWorkflowService,
    ) -> None:
        super().__init__(session)
        self._conversation_service = conversation_service
        self._conversation_event_service = conversation_event_service
        self._orchestrator = orchestrator
        self._action_workflow_service = action_workflow_service

    async def chat(
        self,
        *,
        user_id: UserId,
        conversation_id: ConversationId,
        message: str,
        request_id: UUID,
        files: tuple[ToolFileDTO, ...] = (),
    ) -> ChatResultDTO:
        """
        Process a chat request.

        Human approval is never awaited inside the request.
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
            # ---------------------------------------------------------
            # 1. Persist user message
            # ---------------------------------------------------------

            user_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                request_id=request_id,
                role=MessageRoleEnum.USER,
                content=message,
            )

            # ---------------------------------------------------------
            # 2. Build orchestration request
            # ---------------------------------------------------------

            orchestration_request = await self._build_chat_request(
                conversation=conversation,
                current_event_id=user_event.id,
                message=message,
                request_id=request_id,
                files=files,
            )

            # ---------------------------------------------------------
            # 3. Delegate orchestration
            # ---------------------------------------------------------

            result = await self._orchestrator.handle(
                request=orchestration_request,
                action_workflow_service=self._action_workflow_service,
            )

            # ---------------------------------------------------------
            # 4. Persist assistant response
            #
            # The assistant event is also persisted when HITL approval
            # is required so the approval state is available in
            # conversation history.
            # ---------------------------------------------------------

            metadata = result.metadata.model_dump(
                mode="json",
            )

            if result.approval is not None:
                metadata["approval"] = result.approval.model_dump(
                    mode="json",
                )

            assistant_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                request_id=request_id,
                parent_event_id=user_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=result.content,
                metadata=metadata,
            )

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
                    "action_required": result.action is not None,
                    "approval_required": result.approval is not None,
                },
            )

            return ChatResultDTO(
                conversation=conversation,
                user_event=user_event,
                assistant_event=assistant_event,
                response=result,
                approval=result.approval,
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
        files: tuple[ToolFileDTO, ...] = (),
    ) -> AsyncIterator[ChatStreamChunkDTO]:
        """
        Stream a chat response.

        Action processing happens inside the orchestrator after the
        final orchestration result is produced.
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
                files=files,
            )

            stream = self._orchestrator.stream(
                request=orchestration_request,
                action_workflow_service=self._action_workflow_service,
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

            # ---------------------------------------------------------
            # Persist assistant response
            #
            # Approval information is stored in the assistant event
            # metadata so it is available in conversation history.
            # ---------------------------------------------------------

            metadata = final_response.metadata.model_dump(
                mode="json",
            )

            if final_response.approval is not None:
                metadata["approval"] = final_response.approval.model_dump(
                    mode="json",
                )

            assistant_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                request_id=request_id,
                parent_event_id=user_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=final_response.content,
                metadata=metadata,
            )

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
                    "approval_required": final_response.approval is not None,
                },
            )

        except asyncio.CancelledError:
            await self.rollback()

            logger.info(
                "Chat stream cancelled.",
                extra={
                    "operation": "stream_chat",
                    "request_id": str(request_id),
                    "conversation_id": str(conversation_id),
                    "user_id": str(user_id),
                },
            )

            raise

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
        files: tuple[ToolFileDTO, ...] = (),
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
            attachments=files,
            current_event_id=current_event_id,
        )
