"""
Legal prompt builder.
"""

from __future__ import annotations

from src.agents.prompts.base import BasePromptBuilder
from src.core.dto.agent import AgentRequestDTO
from src.core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from src.core.dto.tool import RetrievedContentDTO
from src.core.enums import MessageRoleEnum


class LegalPromptBuilder(BasePromptBuilder):
    """
    Prompt builder for the Legal agent.
    """

    template_name = "legal.md"

    def __init__(self) -> None:
        self._system_prompt = self.load_template()

    def build(
        self,
        *,
        request: AgentRequestDTO,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ],
    ) -> LLMRequestDTO:
        """
        Build a provider-independent LLM request.
        """

        messages: list[LLMMessageDTO] = [
            LLMMessageDTO(
                role=MessageRoleEnum.SYSTEM,
                content=self._system_prompt,
            ),
        ]

        if context:
            messages.append(
                LLMMessageDTO(
                    role=MessageRoleEnum.SYSTEM,
                    content=self.build_context(
                        context=context,
                    ),
                ),
            )

        messages.extend(
            LLMMessageDTO(
                role=message.role,
                content=message.content,
            )
            for message in request.conversation.messages
        )

        return LLMRequestDTO(
            messages=tuple(messages),
        )
