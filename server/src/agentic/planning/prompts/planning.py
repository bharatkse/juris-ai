"""
Planning prompt builder.
"""

from __future__ import annotations

from agentic.agents.prompts.user_memory import render_user_memory_block
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

        memory_block = render_user_memory_block(request.user_memory)

        return LLMRequestDTO(
            messages=(
                LLMMessageDTO(
                    role=MessageRoleEnum.SYSTEM,
                    content=self._system_prompt,
                ),
                # Its own message, after the system prompt and before the
                # history -- never a history message, which would let it
                # be treated as something the user just said.
                *(
                    (
                        LLMMessageDTO(
                            role=MessageRoleEnum.SYSTEM,
                            content=memory_block,
                        ),
                    )
                    if memory_block
                    else ()
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
