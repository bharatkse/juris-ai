"""
Intent prompt builder.
"""

from __future__ import annotations

from core.models.planning import PlanningRequest
from src.core.enums import MessageRole
from src.core.models import GenerateRequest, Message

from .base import BasePromptBuilder


class IntentPromptBuilder(
    BasePromptBuilder[PlanningRequest],
):
    """
    Builds prompts for intent classification.
    """

    def __init__(
        self,
    ) -> None:
        self._system_prompt = self.load_template(
            "intent.md",
        )

    def build(
        self,
        *,
        request: PlanningRequest,
    ) -> GenerateRequest:
        """
        Build an intent classification request.
        """

        return GenerateRequest(
            messages=(
                Message(
                    role=MessageRole.SYSTEM,
                    content=self._system_prompt,
                ),
                *request.conversation.messages,
            ),
        )
