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

    async def stream(
        self,
        *,
        request: AgentRequestDTO,
    ) -> AsyncIterator[AgentStreamChunkDTO]:
        """
        Stream the agent response.

        The same inference policy used by non-streaming generation is
        carried through to the provider-independent request.
        """
        llm_request = await self._build_llm_request(
            request=request,
        )

        async for chunk in self._llm.stream(
            request=llm_request,
        ):
            yield AgentStreamChunkDTO(
                content=chunk.content,
                is_final=chunk.is_final,
                finish_reason=chunk.finish_reason,
                metadata=chunk.metadata,
            )

    async def _build_llm_request(
        self,
        *,
        request: AgentRequestDTO,
    ) -> LLMRequestDTO:
        """
        Build the provider-independent LLM request and attach the
        agent-owned inference intent.

        No retrieval context is sourced here. The graph execution path
        (_reason()) receives context externally via
        AgentExecutionHandle.reasoning_context, populated by TOOL_CALL
        results through the Tool Registry + policy path -- not through
        this agent holding a retriever reference. stream() (the only
        caller of this method) therefore runs with no retrieved
        context, same as before this change since it was already
        unreachable in production.
        """
        llm_request = self._prompt_builder.build(
            request=request,
            context=(),
        )

        return self._apply_inference(
            request=llm_request,
            task=self.inference_task,
            structured_output=True,
        )

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
