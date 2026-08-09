"""
Intent analyzer.
"""

from __future__ import annotations

from src.clients.llm.base import LLMClient
from src.planning.models import Intent, PlanningRequest
from src.planning.prompts.intent import IntentPromptBuilder


class IntentAnalyzer:
    """
    Classifies the user's intent from a planning request.
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_builder: IntentPromptBuilder,
    ) -> None:
        self._llm = llm_client
        self._prompt_builder = prompt_builder

    async def analyze(
        self,
        *,
        request: PlanningRequest,
    ) -> Intent:
        """
        Analyze the planning request.
        """

        llm_request = self._prompt_builder.build(
            request=request,
        )

        return await self._llm.generate_structured(
            request=llm_request,
            response_model=Intent,
        )
