"""
Base AI agent.

The agent owns inference intent, while the prompt builder remains
provider-independent and the LLM client remains responsible for provider
translation.
"""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from adapters.clients.llm.base import LLMClient
from agentic.agents.prompts.base import BasePromptBuilder
from agentic.agents.prompts.token_budget import DEFAULT_RESERVED_OUTPUT_TOKENS
from agentic.decisions.schemas import AgentDecision
from core.dto.agent import (
    AgentMetadataDTO,
    AgentRequestDTO,
)
from core.dto.clients.llm import LLMRequestDTO
from core.dto.inference import InferencePolicy, LLMTask
from core.dto.tool import RetrievedContentDTO


class BaseAgent:
    """
    Base class for AI agents.

    Inference intent belongs to the agent because the agent knows whether
    an LLM call is a structured decision, factual answer, summarization,
    classification, or another application-level task.

    The agent does not know provider-specific request fields.
    """

    metadata: ClassVar[AgentMetadataDTO]

    # Concrete agents may override this when their user-facing generation
    # has a different inference intent.
    inference_task: ClassVar[LLMTask] = LLMTask.FACTUAL_ANSWER

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_builder: BasePromptBuilder,
        inference_policy: InferencePolicy | None = None,
    ) -> None:
        self._llm = llm_client
        self._prompt_builder = prompt_builder
        self._inference_policy = inference_policy or InferencePolicy()

    @property
    def llm(
        self,
    ) -> LLMClient:
        """
        Return the configured language model client.
        """
        return self._llm

    async def _reason(
        self,
        *,
        request: AgentRequestDTO,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ] = (),
    ) -> AgentDecision:
        """
        Produce one validated agent decision.

        This method performs reasoning only. It does not execute tools,
        delegate to another agent, or perform concrete actions.

        Structured decision inference uses the low-temperature TOOL_CALL
        task profile to make the decision generation deterministic.
        """
        llm_request = self._prompt_builder.build(
            request=request,
            context=context,
            model=self._llm.model,
            reserved_output_tokens=self._reserved_output_tokens(),
        )

        llm_request = self._apply_inference(
            request=llm_request,
            task=LLMTask.STRUCTURED_DECISION,
            structured_output=True,
        )

        return await self._llm.generate_structured(
            request=llm_request,
            response_model=AgentDecision,
        )

    def _reserved_output_tokens(self) -> int:
        """
        Output-token reservation used when budgeting the prompt.

        The full InferencePolicy resolution (which may pick a
        task-specific max_output_tokens) doesn't happen until
        _apply_inference, after the prompt is already built -- see
        _reason()/_build_llm_request() above. This uses the policy's
        configured default as a reasonable stand-in rather than
        resolving the full config twice; a task-specific override that
        differs from the default isn't reflected in the pre-build
        budget.
        """

        return self._inference_policy.default_max_output_tokens or DEFAULT_RESERVED_OUTPUT_TOKENS

    def _apply_inference(
        self,
        *,
        request: LLMRequestDTO,
        task: LLMTask,
        structured_output: bool,
    ) -> LLMRequestDTO:
        """
        Resolve task intent into provider-independent inference settings.

        Model routing/cascading is intentionally not performed here.
        That responsibility belongs to the later LLM routing scope.
        """
        inference = self._inference_policy.resolve(
            task,
            model=request.inference.model,
            top_p=request.inference.top_p,
            max_output_tokens=request.inference.max_output_tokens,
            structured_output=structured_output,
        )

        return replace(
            request,
            inference=inference,
        )
