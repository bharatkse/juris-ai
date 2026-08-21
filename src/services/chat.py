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
from src.orchestration.orchestrator import AIOrchestrator
from src.orchestration.schemas.request import OrchestratorRequest
from src.services.action_workflow import ActionWorkflowService
from src.services.base import BaseService
from src.services.conversation import ConversationService
from src.services.conversation_event import ConversationEventService
from src.services.internal_dto.chat import ChatResultDTO
from src.services.internal_dto.stream import ChatStreamChunkDTO

if TYPE_CHECKING:
    from src.core.dto.tool import ToolFileDTO
    from src.db.models.conversation import Conversation as ConversationModel

logger = get_logger(__name__)


class ChatService(BaseService):
    """
    Coordinates chat interactions and owns the database transaction.

    ChatService is responsible for:

    - conversation persistence,
    - orchestration,
    - action workflow coordination,
    - transaction boundaries.

    Action persistence and action authorization are delegated to
    ActionWorkflowService.

    Approval lifecycle rules remain owned by
    ApprovalLifecycleService.
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
        super().__init__(
            session=session,
        )

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

        If orchestration produces an action, the action is passed
        through ActionWorkflowService.

        When human approval is required, the approval result is
        returned and the request does not continue to execution.
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
                files=files,
            )

            result = await self._orchestrator.handle(
                request=orchestration_request,
            )

            approval = None

            # ---------------------------------------------------------
            # Action workflow
            #
            # The orchestrator only proposes the action.
            #
            # ActionWorkflowService:
            #
            #   ActionRequestDTO
            #       ↓
            #   persist action
            #       ↓
            #   authorize action
            #       ↓
            #   optional approval
            # ---------------------------------------------------------

            if result.action is not None:
                workflow_result = await self._action_workflow_service.authorize(
                    event_id=user_event.id,
                    user_id=user_id,
                    action=result.action,
                )

                approval = workflow_result.approval

                logger.info(
                    "Action workflow completed.",
                    extra={
                        "operation": "action_workflow",
                        "request_id": str(request_id),
                        "conversation_id": str(conversation.id),
                        "event_id": workflow_result.action.event_id,
                        "action_id": workflow_result.action.action_id,
                        "tool_name": workflow_result.action.tool_name,
                        "action_type": (workflow_result.action.action_type.value),
                        "approval_required": (workflow_result.approval_required),
                        "approval_id": (
                            str(approval.approval_id) if approval is not None else None
                        ),
                    },
                )

                # -----------------------------------------------------
                # Approval required.
                #
                # Do not create the normal assistant event here.
                # The action is waiting for human approval.
                # -----------------------------------------------------

                if workflow_result.approval_required:
                    await self.commit()

                    logger.info(
                        "Chat request waiting for approval.",
                        extra={
                            "operation": "approval_required",
                            "request_id": str(request_id),
                            "conversation_id": str(conversation.id),
                            "user_id": str(user_id),
                            "action_id": (workflow_result.action.action_id),
                            "approval_id": str(
                                approval.approval_id,
                            ),
                        },
                    )

                    return ChatResultDTO(
                        conversation=conversation,
                        user_event=user_event,
                        assistant_event=None,
                        response=result.content,
                        approval=approval,
                    )

            # ---------------------------------------------------------
            # No approval required.
            #
            # Either this was normal chat or the action was
            # authorized without human approval.
            # ---------------------------------------------------------

            assistant_event = await self._conversation_event_service.create(
                conversation_id=conversation.id,
                request_id=request_id,
                parent_event_id=user_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=result.content,
                metadata=result.metadata.model_dump(
                    mode="json",
                ),
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
                    "approval_required": False,
                },
            )

            return ChatResultDTO(
                conversation=conversation,
                user_event=user_event,
                assistant_event=assistant_event,
                response=result.content,
                approval=None,
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

        Action workflow processing should happen after the
        orchestrator produces its final result.
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
        )
