"""
Planning prompt builder.
"""

from __future__ import annotations

from src.core.enums import MessageRole
from src.core.models import GenerateRequest, Message
from src.core.models.planning import PlanningPromptRequest

from .base import BasePromptBuilder


class PlanningPromptBuilder(
    BasePromptBuilder[PlanningPromptRequest],
):
    """
    Builds prompts for execution plan generation.
    """

    def __init__(
        self,
    ) -> None:
        self._system_prompt = self.load_template(
            "execution_plan.md",
        )

    def build(
        self,
        *,
        request: PlanningPromptRequest,
    ) -> GenerateRequest:
        """
        Build a planning request for the language model.
        """

        return GenerateRequest(
            messages=(
                Message(
                    role=MessageRole.SYSTEM,
                    content=self._system_prompt,
                ),
                Message(
                    role=MessageRole.SYSTEM,
                    content=f"Detected intent: {request.intent.value}",
                ),
                *request.planning_request.conversation.messages,
            ),
        )
