"""
Legal AI agent.
"""

from __future__ import annotations

from typing import final

from adapters.clients.llm.base import LLMClient
from agentic.agents.base import BaseAgent
from agentic.agents.prompts.legal import LegalPromptBuilder
from core.dto.agent import AgentMetadataDTO
from core.dto.inference import InferencePolicy, LLMTask


@final
class LegalAgent(BaseAgent):
    """
    General-purpose legal assistant.
    """

    metadata = AgentMetadataDTO(
        name="legal",
        description=(
            "General-purpose legal assistant. Use for legal questions, legal "
            "research, laws and regulations, case law and general legal guidance."
        ),
        capabilities=(
            "legal_research",
            "legal_qa",
        ),
        tools=("retriever",),
    )
    inference_task = LLMTask.FACTUAL_ANSWER

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        inference_policy: InferencePolicy | None = None,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            prompt_builder=LegalPromptBuilder(),
            inference_policy=inference_policy,
        )
