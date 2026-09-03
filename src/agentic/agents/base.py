"""
Base AI agent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import ClassVar

from adapters.clients.llm.base import LLMClient
from agentic.agents.prompts.base import BasePromptBuilder
from agentic.tools.retrieval import RetrieverTool
from core.dto.agent import (
    AgentMetadataDTO,
    AgentRequestDTO,
    AgentResponseDTO,
    AgentStreamChunkDTO,
)
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.clients.llm import LLMRequestDTO
from core.dto.tool import RetrievedContentDTO, ToolRequestDTO
from core.enums import ActorTypeEnum, MessageRoleEnum, RetrievalSourceEnum
from core.models.agent import AgentResponseSchema
from core.models.message import AgentMessageSchema


class BaseAgent:
    """
    Base class for AI agents.
    """

    metadata: ClassVar[AgentMetadataDTO]

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_builder: BasePromptBuilder,
        retriever: RetrieverTool | None = None,
    ) -> None:
        self._llm = llm_client
        self._prompt_builder = prompt_builder
        self._retriever = retriever

    @property
    def llm(
        self,
    ) -> LLMClient:
        """
        Return the configured language model client.
        """

        return self._llm

    async def run(
        self,
        *,
        request: AgentRequestDTO,
    ) -> AgentResponseDTO:
        """
        Execute the agent.

        The LLM returns a structured agent response so that
        concrete actions can be represented explicitly.
        """

        llm_request = await self._build_llm_request(
            request=request,
        )

        response = await self._llm.generate_structured(
            request=llm_request,
            response_model=AgentResponseSchema,
        )

        action = None

        if response.action is not None:
            action = AgentActionRequestDTO(
                execution_id=request.context.execution_id,
                thread_id=request.context.thread_id,
                conversation_event_id=request.context.conversation_event_id,
                agent_id=self.metadata.name,
                action_type=response.action.action_type,
                actor_type=ActorTypeEnum.AGENT,
                tool_name=response.action.tool_name,
                target_agent_id=response.action.target_agent_id,
                resource_type=response.action.resource_type,
                resource_id=response.action.resource_id,
                parameters=response.action.parameters,
                reason=response.action.reason,
            )

        return AgentResponseDTO(
            agent_name=self.metadata.name,
            content=response.content,
            metadata=response.metadata,
            action=action,
        )

    async def stream(
        self,
        *,
        request: AgentRequestDTO,
    ) -> AsyncIterator[AgentStreamChunkDTO]:
        """
        Stream the agent response.
        """

        llm_request = await self._build_llm_request(
            request=request,
        )

        async for chunk in self._llm.stream(
            request=llm_request,
        ):
            yield AgentStreamChunkDTO(
                content=chunk.content,
                is_final=chunk.is_final,
                finish_reason=chunk.finish_reason,
                metadata=chunk.metadata,
            )

    async def _retrieve_context(
        self,
        *,
        request: AgentRequestDTO,
    ) -> tuple[
        RetrievedContentDTO,
        ...,
    ]:
        """
        Retrieve contextual information.
        """

        if self._retriever is None:
            return ()

        tool_request = self._build_tool_request(
            request=request,
        )
        content = await self._retriever.execute(
            query=tool_request.query,
        )

        if content in {
            "No relevant content found.",
            "Retrieval failed — please try again.",
        }:
            return ()

        return (
            RetrievedContentDTO(
                source=RetrievalSourceEnum.DOCUMENT,
                source_name=self._retriever.name,
                content=content,
            ),
        )

    @staticmethod
    def _build_tool_request(
        *,
        request: AgentRequestDTO,
    ) -> ToolRequestDTO:
        """
        Build a retrieval tool request.
        """

        user_message = next(
            message
            for message in reversed(
                request.conversation.messages,
            )
            if message.role is MessageRoleEnum.USER
        )

        return ToolRequestDTO(
            query=user_message.content,
            uploaded_files=request.context.uploaded_files,
        )

    async def _build_llm_request(
        self,
        *,
        request: AgentRequestDTO,
    ) -> LLMRequestDTO:
        """
        Build the provider-independent LLM request.
        """

        context = await self._retrieve_context(
            request=request,
        )

        return self._prompt_builder.build(
            request=request,
            context=context,
        )

    async def handle_message(
        self,
        *,
        message: AgentMessageSchema,
    ) -> object:
        """
        Handle an agent-to-agent collaboration message.

        Subclasses may override this to implement collaboration-specific
        capabilities.
        """

        raise NotImplementedError(
            f"Agent '{self.metadata.name}' does not support " "agent-to-agent collaboration.",
        )
