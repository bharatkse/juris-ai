"""
Chat service.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import BaseAgent
from src.agents.models import AgentMessage, AgentRequest, AgentResponse
from src.core.enums import MessageRole
from src.core.exceptions import NotFoundError
from src.db.models.conversation import Conversation
from src.db.models.conversation_event import ConversationEvent
from src.repositories.conversation import ConversationRepository
from src.repositories.conversation_event import ConversationEventRepository
from src.services.base import BaseService
from src.services.results.chat import ChatResult
from src.services.results.stream import ChatStreamChunk


class ChatService(BaseService):
    """
    Business logic for chat interactions.
    """

    def __init__(
        self,
        session: AsyncSession,
        conversation_repository: ConversationRepository,
        event_repository: ConversationEventRepository,
        agent: BaseAgent,
    ) -> None:
        super().__init__(session)

        self._conversation_repository = conversation_repository
        self._event_repository = event_repository
        self._agent = agent

    async def chat(
        self,
        *,
        conversation_id: str,
        message: str,
    ) -> ChatResult:
        """
        Process a chat request.
        """

        conversation = await self._get_conversation(
            conversation_id,
        )

        user_event = await self._create_user_event(
            conversation=conversation,
            message=message,
        )

        request = AgentRequest(
            question=message,
            history=[],
        )

        agent_response = await self._agent.answer(request)

        assistant_event = await self._create_assistant_event(
            conversation=conversation,
            parent_event=user_event,
            response=agent_response,
        )

        await self.commit()

        return ChatResult(
            conversation=conversation,
            user_event=user_event,
            assistant_event=assistant_event,
        )

    async def stream_chat(
        self,
        *,
        conversation_id: str,
        message: str,
    ) -> AsyncIterator[ChatStreamChunk]:
        """
        Stream a chat response.
        """

        conversation = await self._get_conversation(
            conversation_id,
        )

        user_event = await self._create_user_event(
            conversation=conversation,
            message=message,
        )

        #
        # Persist the user's message immediately.
        #
        await self.commit()

        request = await self._build_agent_request(
            conversation=conversation,
            message=message,
        )

        stream = self._agent.stream_answer(
            request=request,
        )

        async for chunk in stream:
            yield ChatStreamChunk(
                content=chunk.content,
                is_final=chunk.is_final,
                metadata=chunk.metadata,
            )

        await self._create_assistant_event(
            conversation=conversation,
            parent_event=user_event,
            response=stream.response,
        )

        await self.commit()

    async def _build_agent_request(
        self,
        *,
        conversation: Conversation,
        message: str,
    ) -> AgentRequest:
        """
        Build the request sent to the AI agent.
        """

        #
        # TODO:
        # Load recent conversation events and convert them
        # into AgentMessage instances.
        #
        history: list[AgentMessage] = []

        return AgentRequest(
            question=message,
            history=history,
        )

    async def _get_conversation(
        self,
        conversation_id: str,
    ) -> Conversation:
        """
        Retrieve an active conversation.
        """

        conversation = await self._conversation_repository.get(
            conversation_id,
        )

        if conversation is None:
            raise NotFoundError("Conversation not found.")

        if not conversation.is_active:
            raise NotFoundError("Conversation is inactive.")

        return conversation

    async def _create_user_event(
        self,
        *,
        conversation: Conversation,
        message: str,
    ) -> ConversationEvent:
        """
        Persist the user's event.
        """

        return await self._event_repository.create(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=message,
        )

    async def _create_assistant_event(
        self,
        *,
        conversation: Conversation,
        parent_event: ConversationEvent,
        response: AgentResponse,
    ) -> ConversationEvent:
        """
        Persist the assistant event.
        """

        return await self._event_repository.create(
            conversation_id=conversation.id,
            parent_event_id=parent_event.id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            metadata={
                "provider": response.provider,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "latency_ms": response.latency_ms,
                "usage": (
                    {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                    if response.usage
                    else None
                ),
                **response.metadata,
            },
        )
