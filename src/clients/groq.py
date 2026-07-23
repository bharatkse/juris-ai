"""
Groq LLM client.
"""

from __future__ import annotations

from groq import AsyncGroq

from src.clients.base import BaseLLMClient
from src.clients.models import LLMMessage, LLMResponse, LLMTokenUsage
from src.core.config import settings


class GroqClient(BaseLLMClient):
    """
    Groq LLM provider.
    """

    PROVIDER = "groq"

    def __init__(self) -> None:
        self._client = AsyncGroq(
            api_key=settings.GROQ_API_KEY.get_secret_value(),
        )

        self._model = settings.GROQ_MODEL

    async def generate(
        self,
        *,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a completion using Groq.
        """

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": message.role.value,
                    "content": message.content,
                }
                for message in messages
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]

        usage = None

        if response.usage:
            usage = LLMTokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return LLMResponse(
            content=choice.message.content or "",
            provider=self.PROVIDER,
            model=response.model,
            finish_reason=choice.finish_reason,
            usage=usage,
        )
