"""
LLM-backed execution plan generator.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

from langsmith import traceable

from adapters.clients.llm.base import LLMClient
from adapters.observability.logger import get_logger
from agentic.planning.capabilities import AgentCapabilityCatalog
from agentic.planning.prompts.planning import PlanningPromptBuilder
from core.deadline import deadline_within, remaining_seconds
from core.dto.clients.llm import LLMRequestDTO
from core.dto.inference import InferencePolicy, LLMTask
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO, PlanningRequestDTO
from core.exceptions.planning import PlanningTimeoutError
from core.models.planning import ExecutionPlanResponseSchema

log = get_logger(__name__)

# Default for settings.llm.PLANNER_TIMEOUT_S (review R18).
DEFAULT_PLANNER_TIMEOUT_SECONDS = 120.0


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
        timeout_seconds: float = DEFAULT_PLANNER_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")

        self._llm = llm_client
        # Bound on the planner's LLM call (settings.llm.PLANNER_TIMEOUT_S,
        # review R18): a hung or very slow local model must not hold the
        # request open indefinitely.
        self._timeout_seconds = timeout_seconds
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

        response = await self._generate_within_timeout(llm_request)

        return self._to_execution_plan(
            response=response,
        )

    async def _generate_within_timeout(
        self,
        llm_request: LLMRequestDTO,
    ) -> ExecutionPlanResponseSchema:
        """
        The planner's LLM call, bounded by the planner timeout or the
        request's deadline, whichever is closer. The call runs under that
        deadline (core.deadline), so a FailoverLLMClient around the
        planner's client can see how long is left.
        """

        remaining = remaining_seconds()
        timeout = (
            self._timeout_seconds if remaining is None else min(self._timeout_seconds, remaining)
        )

        try:
            with deadline_within(self._timeout_seconds):
                async with asyncio.timeout(max(timeout, 0.0)):
                    return await self._llm.generate_structured(
                        request=llm_request,
                        response_model=ExecutionPlanResponseSchema,
                    )
        except TimeoutError as exc:
            log.warning(
                "Planner LLM call timed out.",
                extra={"operation": "generate_plan", "timeout_seconds": round(timeout, 1)},
            )
            raise PlanningTimeoutError(timeout_seconds=timeout) from exc

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
