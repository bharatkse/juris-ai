"""
Planning prompt builder.
"""

from __future__ import annotations

from src.core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from src.core.dto.planning import PlanningRequestDTO
from src.core.enums import IntentEnum, MessageRoleEnum

from .base import BasePromptBuilder


class PlanningPromptBuilder(
    BasePromptBuilder[PlanningRequestDTO],
):
    """
    Builds prompts for execution plan generation.
    """

    template_name = "planning.md"

    def __init__(
        self,
    ) -> None:
        self._system_prompt = self.load_template(self.template_name)

    def build(
        self,
        *,
        request: PlanningRequestDTO,
        intent: IntentEnum,
    ) -> LLMRequestDTO:
        """
        Build an execution planning request.
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
                    content=(
                        f"Detected intent: {intent.value}\n\n" f"User request:\n{request.message}"
                    ),
                ),
            ),
        )
