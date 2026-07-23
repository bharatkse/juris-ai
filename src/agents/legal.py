"""
Legal AI agent.
"""

from __future__ import annotations

import time

from src.agents.base import BaseAgent
from src.agents.models import AgentResponse
from src.clients.base import BaseLLMClient
from src.clients.models import LLMMessage
from src.core.enums import MessageRole
from src.prompts.legal import LEGAL_SYSTEM_PROMPT


class LegalAgent(BaseAgent):
    """
    AI agent responsible for answering legal questions.
    """

    def __init__(
        self,
        client: BaseLLMClient,
    ) -> None:
        self._client = client

    async def answer(
        self,
        *,
        question: str,
    ) -> AgentResponse:
        """
        Answer a legal question.
        """

        started_at = time.perf_counter()

        response = await self._client.generate(
            messages=[
                LLMMessage(
                    role=MessageRole.SYSTEM,
                    content=LEGAL_SYSTEM_PROMPT,
                ),
                LLMMessage(
                    role=MessageRole.USER,
                    content=question,
                ),
            ],
        )

        latency_ms = int(
            (time.perf_counter() - started_at) * 1000,
        )

        return AgentResponse(
            content=response.content,
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            latency_ms=latency_ms,
            usage=response.usage,
            metadata=response.metadata,
        )
