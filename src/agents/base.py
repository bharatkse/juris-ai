"""
Base AI agent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from src.agents.prompts.base import BasePromptBuilder
from src.clients.llm.base import LLMClient
from src.core.enums import MessageRole
from src.core.models import GenerateRequest
from src.core.models.agent import AgentRequest, AgentResponse, AgentStreamChunk
from src.core.models.tool import RetrievedContent, ToolRequest
from src.tools.retrieval import RetrieverTool


class BaseAgent:
    """
    Base class for AI agents.
    """

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
        request: AgentRequest,
    ) -> AgentResponse:
        """
        Execute the agent.
        """

        llm_request = await self._build_generate_request(
            request=request,
        )

        response = await self._llm.generate(
            request=llm_request,
        )

        return AgentResponse(
            content=response.content,
            metadata=response.metadata,
        )

    async def stream(
        self,
        *,
        request: AgentRequest,
    ) -> AsyncIterator[AgentStreamChunk]:
        """
        Stream the agent response.
        """

        llm_request = await self._build_generate_request(
            request=request,
        )

        async for chunk in self._llm.stream(
            request=llm_request,
        ):
            yield AgentStreamChunk(
                content=chunk.content,
                is_final=chunk.is_final,
                finish_reason=chunk.finish_reason,
                metadata=chunk.metadata,
            )

    async def _build_generate_request(
        self,
        *,
        request: AgentRequest,
    ) -> GenerateRequest:
        """
        Build an LLM generation request.
        """

        context = await self._retrieve_context(
            request=request,
        )

        return self._prompt_builder.build(
            request=request,
            context=context,
        )

    async def _retrieve_context(
        self,
        *,
        request: AgentRequest,
    ) -> tuple[
        RetrievedContent,
        ...,
    ]:
        """
        Retrieve contextual information.
        """

        if self._retriever is None:
            return ()

        response = await self._retriever.run(
            request=self._build_tool_request(
                request=request,
            ),
        )

        return response.results

    @staticmethod
    def _build_tool_request(
        *,
        request: AgentRequest,
    ) -> ToolRequest:
        """
        Build a retrieval tool request.
        """

        user_message = next(
            message
            for message in reversed(
                request.conversation.messages,
            )
            if message.role is MessageRole.USER
        )

        return ToolRequest(
            query=user_message.content,
            uploaded_files=request.context.uploaded_files,
        )
