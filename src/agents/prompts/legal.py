"""
Legal prompt builder.
"""

from __future__ import annotations

from src.agents.prompts.base import BasePromptBuilder
from src.core.enums import MessageRole
from src.core.models import GenerateRequest, Message
from src.core.models.agent import AgentRequest
from src.core.models.tool import RetrievedContent


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
        request: AgentRequest,
        context: tuple[
            RetrievedContent,
            ...,
        ],
    ) -> GenerateRequest:
        """
        Build a language model generation request.
        """

        messages: list[Message] = [
            Message(
                role=MessageRole.SYSTEM,
                content=self.load_template(),
            ),
        ]

        if context:
            messages.append(
                Message(
                    role=MessageRole.SYSTEM,
                    content=self.build_context(
                        context=context,
                    ),
                ),
            )

        messages.extend(
            request.conversation.messages,
        )

        return GenerateRequest(
            messages=tuple(messages),
        )
