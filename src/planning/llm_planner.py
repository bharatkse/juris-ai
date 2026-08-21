"""
LLM-backed execution plan generator.
"""

from __future__ import annotations

from langsmith import traceable

from src.clients.llm.base import LLMClient
from src.core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO, PlanningRequestDTO
from src.core.schemas.planning import ExecutionPlanResponseSchema
from src.planning.prompts.planning import PlanningPromptBuilder


class LLMPlanGenerator:
    """
    Generates execution plans using a language model.

    The language model is responsible for generating the
    complete planning result in a single structured call,
    including:

        - intent,
        - execution mode,
        - execution steps,
        - step dependencies,
        - plan metadata.
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_builder: PlanningPromptBuilder,
    ) -> None:
        self._llm = llm_client
        self._prompt_builder = prompt_builder

    @traceable(
        name="planner",
        run_type="chain",
    )
    async def generate(
        self,
        *,
        request: PlanningRequestDTO,
    ) -> ExecutionPlanDTO:
        """
        Generate an execution plan for the supplied request.

        The LLM determines the intent and execution mode
        as part of the same structured response.
        """

        llm_request = self._prompt_builder.build(
            request=request,
        )

        response = await self._llm.generate_structured(
            request=llm_request,
            response_model=ExecutionPlanResponseSchema,
        )

        return self._to_execution_plan(
            response=response,
        )

    @staticmethod
    def _to_execution_plan(
        *,
        response: ExecutionPlanResponseSchema,
    ) -> ExecutionPlanDTO:
        """
        Convert the provider-facing Pydantic response
        into the domain execution plan.
        """

        return ExecutionPlanDTO(
            intent=response.intent,
            mode=response.mode,
            steps=tuple(
                ExecutionStepDTO(
                    id=step.id,
                    agent=step.agent,
                    instruction=step.instruction,
                    depends_on=step.depends_on,
                    stage=step.stage,
                    arguments=step.arguments,
                    action=step.action,
                )
                for step in response.steps
            ),
            metadata=response.metadata,
        )
