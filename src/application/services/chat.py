"""
Chat service.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from adapters.observability.logger import get_logger
from agentic.orchestration.schemas.request import OrchestratorRequest
from agentic.orchestration.schemas.response import Citation, OrchestratorResponse, Source
from application.services.base import BaseService
from application.services.conversation_summarization import (
    UNSUMMARIZED_EVENT_LIMIT,
)
from application.services.internal_dto.chat import ChatResultDTO
from application.services.internal_dto.stream import ChatStreamChunkDTO
from core.enums import MessageRoleEnum
from core.models.conversation import ConversationMessageSchema
from core.types import ConversationEventId, ConversationId, UserId

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.models.conversation import (
        Conversation as ConversationModel,
    )
    from adapters.persistence.sqlalchemy.models.conversation_event import (
        ConversationEvent,
    )
    from agentic.orchestration.orchestrator import AIOrchestrator
    from application.services.action_workflow import ActionWorkflowService
    from application.services.compliance_log import ComplianceLogService
    from application.services.conversation import ConversationService
    from application.services.conversation_event import ConversationEventService
    from application.services.conversation_summarization import (
        ConversationSummarizationService,
    )
    from application.services.usage import UsageService
    from core.dto.tool import ToolFileDTO

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
        usage_service: UsageService,
        conversation_summarization_service: ConversationSummarizationService,
        compliance_log_service: ComplianceLogService,
    ) -> None:
        super().__init__(session)
        self._conversation_service = conversation_service
        self._conversation_event_service = conversation_event_service
        self._orchestrator = orchestrator
        self._action_workflow_service = action_workflow_service
        self._usage_service = usage_service
        self._conversation_summarization_service = conversation_summarization_service
        self._compliance_log_service = compliance_log_service

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
            user_event = await self._persist_user_message(
                conversation=conversation,
                request_id=request_id,
                message=message,
                user_id=user_id,
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
                action_workflow_service=self._action_workflow_service,
            )

            # The assistant event is also persisted when HITL approval
            # is required so the approval state is available in
            # conversation history.
            assistant_event = await self._persist_assistant_response(
                user_id=user_id,
                conversation=conversation,
                request_id=request_id,
                user_event=user_event,
                response=result,
            )

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

        Persistence/compliance/usage on completion go through the same
        _persist_user_message()/_persist_assistant_response() helpers
        chat() uses -- this is what keeps this method at parity with
        chat() (compliance logging both ways, usage recording) rather
        than the two silently drifting apart again the way they did
        before this fix.
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
            user_event = await self._persist_user_message(
                conversation=conversation,
                request_id=request_id,
                message=message,
                user_id=user_id,
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

            final_response: OrchestratorResponse | None = None

            async for chunk in stream:
                if chunk.is_final:
                    final_response = chunk.response

                yield chunk

            if final_response is None:
                raise RuntimeError(
                    "Streaming completed without a final response.",
                )

            assistant_event = await self._persist_assistant_response(
                user_id=user_id,
                conversation=conversation,
                request_id=request_id,
                user_event=user_event,
                response=final_response,
            )

            logger.info(
                "Chat stream completed.",
                extra={
                    "operation": "stream_chat",
                    "request_id": str(request_id),
                    "conversation_id": str(conversation.id),
                    "user_id": str(user_id),
                    "user_event_id": str(user_event.id),
                    "assistant_event_id": str(assistant_event.id),
                    "action_required": final_response.action is not None,
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

    async def _persist_user_message(
        self,
        *,
        conversation: ConversationModel,
        request_id: UUID,
        message: str,
        user_id: UserId,
    ) -> ConversationEvent:
        """
        Persist the USER conversation event and its matching
        compliance log entry -- the "who asked what, when" half of the
        audit trail. Shared by chat() and stream_chat() so both stay
        in parity by construction, rather than by remembering to keep
        two call sites in sync (stream_chat() previously skipped the
        compliance call here entirely).
        """

        user_event = await self._conversation_event_service.create(
            conversation_id=conversation.id,
            request_id=request_id,
            role=MessageRoleEnum.USER,
            content=message,
        )

        # Same transaction as the assistant event/compliance row
        # _persist_assistant_response() writes below -- its commit()
        # covers both.
        await self._compliance_log_service.record_request_received(
            request_id=request_id,
            user_id=str(user_id),
            tenant_id=str(user_id),
            conversation_id=str(conversation.id),
            conversation_event_id=str(user_event.id),
            message=message,
        )

        return user_event

    async def _persist_assistant_response(
        self,
        *,
        user_id: UserId,
        conversation: ConversationModel,
        request_id: UUID,
        user_event: ConversationEvent,
        response: OrchestratorResponse,
    ) -> ConversationEvent:
        """
        Record usage, persist the ASSISTANT conversation event, log
        the matching compliance entry, and commit -- the "what the
        system decided/returned" half. Shared by chat() and
        stream_chat() for the same reason as _persist_user_message()
        above: this is exactly the logic that drifted out of sync
        between the two before this fix (stream_chat() previously
        skipped both the compliance call and the usage-quota record
        entirely).
        """

        # response.usage is the real, provider-reported token count
        # aggregated across every LLM call made during this
        # orchestration (agentic/execution/aggregation/response.py)
        # -- not an estimate. Best-effort: never blocks or fails the
        # response (see UsageService.record()).
        await self._usage_service.record(
            user_id=user_id,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

        metadata = response.metadata.model_dump(
            mode="json",
        )

        if response.approval is not None:
            metadata["approval"] = response.approval.model_dump(
                mode="json",
            )

        if response.guardrail is not None:
            metadata["guardrail"] = response.guardrail.model_dump(
                mode="json",
            )

        assistant_event = await self._conversation_event_service.create(
            conversation_id=conversation.id,
            request_id=request_id,
            parent_event_id=user_event.id,
            role=MessageRoleEnum.ASSISTANT,
            content=response.content,
            metadata=metadata,
            citations=self._build_citations_payload(
                citations=response.citations,
                sources=response.sources,
            ),
        )

        await self._compliance_log_service.record_response_returned(
            request_id=request_id,
            user_id=str(user_id),
            tenant_id=str(user_id),
            conversation_id=str(conversation.id),
            conversation_event_id=str(assistant_event.id),
            content=response.content,
            citation_count=len(response.citations),
            action_required=response.action is not None,
        )

        await self.commit()

        return assistant_event

    @staticmethod
    def _build_citations_payload(
        *,
        citations: Sequence[Citation],
        sources: Sequence[Source],
    ) -> dict[str, Any] | None:
        """
        Build the {"citations": [...], "sources": [...]} payload
        persisted onto an ASSISTANT conversation_event's ``citations``
        column, or None when the answer carried neither -- a plain
        chat turn with nothing to cite shouldn't grow a stored {}.
        """

        if not citations and not sources:
            return None

        return {
            "citations": [item.model_dump(mode="json") for item in citations],
            "sources": [item.model_dump(mode="json") for item in sources],
        }

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

        History is capped at UNSUMMARIZED_EVENT_LIMIT recent, verbatim
        events; anything older has already been folded into
        conversation.rolling_summary by
        ConversationSummarizationService.ensure_summarized (called just
        below), which is prepended in place of the raw events it
        replaces. This bounds history growth semantically (compression,
        not loss) -- the token budget in agentic/agents/prompts/
        token_budget.py is the separate, final safety net applied
        downstream against whatever model actually serves the request.
        """

        conversation = await self._conversation_summarization_service.ensure_summarized(
            conversation=conversation,
        )

        events = await self._conversation_event_service.list(
            conversation_id=conversation.id,
            limit=UNSUMMARIZED_EVENT_LIMIT,
        )

        history: list[ConversationMessageSchema] = []

        if conversation.rolling_summary:
            history.append(
                ConversationMessageSchema(
                    role=MessageRoleEnum.SYSTEM,
                    content=(
                        "Summary of earlier conversation (older messages "
                        "already folded in):\n" + conversation.rolling_summary
                    ),
                )
            )

        history.extend(
            ConversationMessageSchema(
                content=event.content,
                role=event.role,
            )
            for event in events
            if event.id != current_event_id
        )

        return OrchestratorRequest(
            request_id=request_id,
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            message=message,
            history=history,
            attachments=files,
            current_event_id=current_event_id,
        )
