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
from agentic.tools.retrieval import RetrieverTool
from core.dto.agent import (
    AgentMetadataDTO,
    AgentRequestDTO,
    AgentResponseDTO,
    AgentStreamChunkDTO,
)
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.clients.llm import LLMRequestDTO
from core.dto.inference import InferencePolicy, LLMTask
from core.dto.tool import RetrievedContentDTO, ToolRequestDTO
from core.enums import ActorTypeEnum, MessageRoleEnum, RetrievalSourceEnum
from core.models.agent import AgentResponseSchema
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
        retriever: RetrieverTool | None = None,
        inference_policy: InferencePolicy | None = None,
    ) -> None:
        self._llm = llm_client
        self._prompt_builder = prompt_builder
        self._retriever = retriever
        self._inference_policy = inference_policy or InferencePolicy()

    @property
    def llm(
        self,
    ) -> LLMClient:
        """
        Return the configured language model client.
        """
        return self._llm

    async def run(
        self,
        *,
        request: AgentRequestDTO,
    ) -> AgentResponseDTO:
        """
        Execute the agent.

        The legacy user-facing response path uses structured output.
        Inference policy therefore marks this request as a structured
        application response while retaining the agent's factual-answer
        intent.
        """
        llm_request = await self._build_llm_request(
            request=request,
        )

        response = await self._llm.generate_structured(
            request=llm_request,
            response_model=AgentResponseSchema,
        )

        action = None

        if response.action is not None:
            action = AgentActionRequestDTO(
                execution_id=request.context.execution_id,
                thread_id=request.context.thread_id,
                conversation_event_id=request.context.conversation_event_id,
                agent_id=self.metadata.name,
                action_type=response.action.action_type,
                actor_type=ActorTypeEnum.AGENT,
                tool_name=response.action.tool_name,
                target_agent_id=response.action.target_agent_id,
                resource_type=response.action.resource_type,
                resource_id=response.action.resource_id,
                parameters=response.action.parameters,
                reason=response.action.reason,
            )

        return AgentResponseDTO(
            agent_name=self.metadata.name,
            content=response.content,
            metadata=response.metadata,
            action=action,
        )

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

    async def _retrieve_context(
        self,
        *,
        request: AgentRequestDTO,
    ) -> tuple[
        RetrievedContentDTO,
        ...,
    ]:
        """
        Retrieve contextual information.

        This remains temporarily compatible with the current prompt
        construction. Agent-selected tool execution will replace this
        behavior when the lifecycle runtime is integrated.
        """
        if self._retriever is None:
            return ()

        tool_request = self._build_tool_request(
            request=request,
        )
        content = await self._retriever.execute(
            query=tool_request.query,
        )

        if content in {
            "No relevant content found.",
            "Retrieval failed — please try again.",
        }:
            return ()

        return (
            RetrievedContentDTO(
                source=RetrievalSourceEnum.DOCUMENT,
                source_name=self._retriever.name,
                content=content,
            ),
        )

    async def _build_llm_request(
        self,
        *,
        request: AgentRequestDTO,
    ) -> LLMRequestDTO:
        """
        Build the provider-independent LLM request and attach the
        agent-owned inference intent.
        """
        context = await self._retrieve_context(
            request=request,
        )

        llm_request = self._prompt_builder.build(
            request=request,
            context=context,
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

    @staticmethod
    def _build_tool_request(
        *,
        request: AgentRequestDTO,
    ) -> ToolRequestDTO:
        """
        Build a retrieval tool request.
        """
        user_message = next(
            message
            for message in reversed(
                request.conversation.messages,
            )
            if message.role is MessageRoleEnum.USER
        )

        return ToolRequestDTO(
            query=user_message.content,
            uploaded_files=request.context.uploaded_files,
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
