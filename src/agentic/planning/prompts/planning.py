"""
Planning prompt builder.
"""

from __future__ import annotations

from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.dto.planning import PlanningRequestDTO
from core.enums import MessageRoleEnum

from .base import BasePromptBuilder


class PlanningPromptBuilder(
    BasePromptBuilder[PlanningRequestDTO],
):
    """
    Builds prompts for execution plan generation.

    The planning prompt is responsible for generating the
    complete execution plan in a single LLM call, including
    intent, execution mode, steps, and dependencies.
    """

    template_name = "planning.md"

    def __init__(
        self,
    ) -> None:
        self._system_prompt = self.load_template(
            self.template_name,
        )

    def build(
        self,
        *,
        request: PlanningRequestDTO,
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
                    content=("User request:\n" f"{request.message}"),
                ),
            ),
        )
