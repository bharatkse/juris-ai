"""
LLM-backed execution plan generator.
"""

from __future__ import annotations

from dataclasses import replace

from langsmith import traceable

from adapters.clients.llm.base import LLMClient
from agentic.planning.capabilities import AgentCapabilityCatalog
from agentic.planning.prompts.planning import PlanningPromptBuilder
from core.dto.inference import InferencePolicy, LLMTask
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO, PlanningRequestDTO
from core.models.planning import ExecutionPlanResponseSchema


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
        capability_catalog: AgentCapabilityCatalog,
        inference_policy: InferencePolicy | None = None,
    ) -> None:
        self._llm = llm_client
        self._prompt_builder = prompt_builder
        self._capability_catalog = capability_catalog
        # Planning produces a single structured decision (the execution
        # plan) consumed programmatically, not prose read by a user --
        # same inference intent as an agent's STRUCTURED_DECISION
        # (TOOL_CALL) reasoning. Previously this request carried no
        # inference config at all, silently falling back to
        # LLMInferenceConfig's bare dataclass default (temperature=0.2)
        # instead of a deliberate, low/deterministic setting -- fixed
        # here rather than relying on that default being low enough by
        # accident.
        self._inference_policy = inference_policy or InferencePolicy()

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

        The model is told which agents it may assign steps to and the
        tools each one's policy allows, read from the agent policies at
        call time, so it doesn't plan steps no agent can carry out.
        """

        request = replace(
            request,
            agent_capabilities=await self._capability_catalog.describe(),
        )

        llm_request = self._prompt_builder.build(
            request=request,
        )

        inference = self._inference_policy.resolve(
            LLMTask.STRUCTURED_DECISION,
            model=llm_request.inference.model,
            top_p=llm_request.inference.top_p,
            max_output_tokens=llm_request.inference.max_output_tokens,
            structured_output=True,
        )
        llm_request = replace(llm_request, inference=inference)

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
                )
                for step in response.steps
            ),
            metadata=response.metadata,
        )
