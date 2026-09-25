"""
Planning prompt builder.
"""

from __future__ import annotations

from agentic.agents.prompts.user_memory import render_user_memory_block
from agentic.planning.prompts.agent_capabilities import render_agent_capabilities
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

        The agents the plan may use, and the tools each one's policy
        allows (``request.agent_capabilities``), follow the planning
        instructions as their own SYSTEM message. They're generated per
        request, never written into planning.md, so they match what the
        runtime enforces.
        """

        capabilities_block = render_agent_capabilities(request.agent_capabilities)
        memory_block = render_user_memory_block(request.user_memory)

        return LLMRequestDTO(
            messages=(
                LLMMessageDTO(
                    role=MessageRoleEnum.SYSTEM,
                    content=self._system_prompt,
                ),
                *(
                    (
                        LLMMessageDTO(
                            role=MessageRoleEnum.SYSTEM,
                            content=capabilities_block,
                        ),
                    )
                    if capabilities_block
                    else ()
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
