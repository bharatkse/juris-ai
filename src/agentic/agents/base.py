"""
Base AI agent.

The agent owns inference intent, while the prompt builder remains
provider-independent and the LLM client remains responsible for provider
translation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from typing import ClassVar

from adapters.clients.llm.base import LLMClient
from agentic.agents.prompts.base import BasePromptBuilder
from agentic.agents.prompts.token_budget import DEFAULT_RESERVED_OUTPUT_TOKENS
from agentic.decisions.schemas import AgentDecision
from core.dto.agent import (
    AgentMetadataDTO,
    AgentRequestDTO,
    AgentStreamChunkDTO,
)
from core.dto.clients.llm import LLMRequestDTO
from core.dto.inference import InferencePolicy, LLMTask
from core.dto.tool import RetrievedContentDTO
from core.models.message import AgentMessageSchema


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

    async def stream_final_answer(
        self,
        *,
        request: AgentRequestDTO,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ] = (),
    ) -> AsyncIterator[AgentStreamChunkDTO]:
        """
        Stream the freeform final-answer text for a request the graph
        has already resolved to a FINAL decision
        (agentic.decisions.decision.AgentDecisionType.FINAL, checked
        in agentic/agents/runtime/continuation.py).

        This is a second, separate LLM call from the structured
        AgentDecision _reason() produces above -- a JSON-schema
        -constrained structured response cannot be meaningfully
        streamed token-by-token (a client receiving
        '{"decision_type": "FINAL", "final_r' mid-stream has nothing
        usable). Once the graph already knows the decision is FINAL,
        this method re-generates just the answer text as a plain
        completion instead.

        context is the caller's responsibility to supply -- normally
        AgentExecutionHandle.reasoning_context, the same accumulated
        retrieval/tool-call evidence _reason() already used to reach
        the FINAL decision. Passing it explicitly (default: empty) is
        what makes this method actually grounded rather than a bare,
        contextless completion -- the previous stream() on this class
        hardcoded no context and had zero callers; this replaces it.
        """
        llm_request = self._prompt_builder.build(
            request=request,
            context=context,
            model=self._llm.model,
            reserved_output_tokens=self._reserved_output_tokens(),
        )

        llm_request = self._apply_inference(
            request=llm_request,
            task=self.inference_task,
            structured_output=False,
        )

        async for chunk in self._llm.stream(
            request=llm_request,
        ):
            yield AgentStreamChunkDTO(
                content=chunk.content,
                is_final=chunk.is_final,
                finish_reason=chunk.finish_reason,
                # LLMStreamChunkDTO.metadata is a read-only Mapping
                # (MappingProxyType default); AgentStreamChunkDTO.metadata
                # is a plain, mutable dict -- pre-existing type gap
                # between the two DTOs, only now visible to mypy since
                # fixing LLMClient.stream()'s signature above let it
                # analyze this far. Copying is cheap and correct
                # either way.
                metadata=dict(chunk.metadata),
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

    async def handle_message(
        self,
        *,
        message: AgentMessageSchema,
    ) -> AgentDecision:
        """
        Handle an agent-to-agent collaboration message.

        The collaboration message carries the original agent request
        together with delegation-specific parameters.

        The receiving agent performs one reasoning operation only.
        It does not execute tools, delegate to another agent, or perform
        concrete business actions here. Any resulting decision is returned
        to the parent execution through the collaboration bus.
        """
        payload = message.payload

        request = payload.get("request")

        if not isinstance(request, AgentRequestDTO):
            raise ValueError(
                "Agent collaboration message is missing a valid AgentRequestDTO.",
            )

        parameters = payload.get("parameters", {})

        if not isinstance(parameters, dict):
            raise ValueError(
                "Agent collaboration message parameters must be a dictionary.",
            )

        delegated_request = AgentRequestDTO(
            conversation=request.conversation,
            instruction=request.instruction,
            arguments={
                **request.arguments,
                **parameters,
            },
            context=request.context,
        )

        return await self._reason(
            request=delegated_request,
        )
