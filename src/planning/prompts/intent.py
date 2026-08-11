"""
Intent prompt builder.
"""

from __future__ import annotations

from src.core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from src.core.dto.planning import PlanningRequestDTO
from src.core.enums import MessageRoleEnum

from .base import BasePromptBuilder


class IntentPromptBuilder(
    BasePromptBuilder[PlanningRequestDTO],
):
    """
    Builds prompts for intent classification.
    """

    template_name = "intent.md"

    def __init__(
        self,
    ) -> None:
        self._system_prompt = self.load_template(self.template_name)

    def build(
        self,
        *,
        request: PlanningRequestDTO,
    ) -> LLMRequestDTO:
        """
        Build an intent classification request.
        """

        return LLMRequestDTO(
            messages=(
                LLMMessageDTO(
                    role=MessageRoleEnum.SYSTEM,
                    content=self._system_prompt,
                ),
                *(
                    LLMMessageDTO(
                        role=message.role,
                        content=message.content,
                    )
                    for message in request.history
                ),
                LLMMessageDTO(
                    role=MessageRoleEnum.USER,
                    content=request.message,
                ),
            ),
        )
