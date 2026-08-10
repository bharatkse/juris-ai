"""
LLM-backed execution plan generator.
"""

from __future__ import annotations

from core.models.planning import ExecutionPlan, Intent, PlanningRequest
from src.clients.llm.base import LLMClient
from src.planning.prompts.planning import PlanningPromptBuilder


class LLMPlanGenerator:
    """
    Generates execution plans using a language model.
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_builder: PlanningPromptBuilder,
    ) -> None:
        self._llm = llm_client
        self._prompt_builder = prompt_builder

    async def generate(
        self,
        *,
        request: PlanningRequest,
        intent: Intent,
    ) -> ExecutionPlan:
        """
        Generate an execution plan for the supplied request.
        """

        llm_request = self._prompt_builder.build(
            request=request,
            intent=intent,
        )

        return await self._llm.generate_structured(
            request=llm_request,
            response_model=ExecutionPlan,
        )
