"""
Legal AI agent.
"""

from __future__ import annotations

import time

from src.agents.base import BaseAgent
from src.agents.legal_stream import LegalAgentStream
from src.agents.models import AgentRequest, AgentResponse
from src.agents.stream import AgentStream
from src.clients.base import BaseLLMClient
from src.clients.models import LLMMessage
from src.core.enums import MessageRole


class LegalAgent(BaseAgent):
    """
    AI agent responsible for answering legal questions.
    """

    def __init__(
        self,
        client: BaseLLMClient,
        system_prompt: str,
    ) -> None:
        self._client = client
        self._system_prompt = system_prompt

    def _build_messages(
        self,
        *,
        request: AgentRequest,
    ) -> list[LLMMessage]:
        """
        Build the prompt sent to the LLM.
        """

        messages = [
            LLMMessage(
                role=MessageRole.SYSTEM,
                content=self._system_prompt,
            ),
        ]

        messages.extend(
            LLMMessage(
                role=message.role,
                content=message.content,
            )
            for message in request.history
        )

        messages.append(
            LLMMessage(
                role=MessageRole.USER,
                content=request.question,
            )
        )

        return messages

    async def answer(
        self,
        *,
        request: AgentRequest,
    ) -> AgentResponse:
        """
        Answer a legal question.
        """

        started_at = time.perf_counter()

        response = await self._client.generate(
            messages=self._build_messages(request),
            temperature=0.2,
        )

        latency_ms = int(
            (time.perf_counter() - started_at) * 1000,
        )

        return AgentResponse(
            content=response.content,
            provider=self._client.provider,
            model=self._client.model,
            finish_reason=response.finish_reason,
            latency_ms=latency_ms,
            usage=response.usage,
            metadata=response.metadata,
        )

    def stream_answer(
        self,
        request: AgentRequest,
    ) -> AgentStream:
        """
        Stream an answer.
        """

        return LegalAgentStream(
            client=self._client,
            messages=self._build_messages(request=request),
        )
