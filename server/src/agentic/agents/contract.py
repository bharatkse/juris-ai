"""
Contract AI agent.
"""

from __future__ import annotations

from typing import final

from adapters.clients.llm.base import LLMClient
from agentic.agents.base import BaseAgent
from agentic.agents.prompts.contract import ContractPromptBuilder
from core.dto.agent import AgentMetadataDTO
from core.dto.inference import InferencePolicy, LLMTask


@final
class ContractAgent(BaseAgent):
    """
    Contract analysis specialist.
    """

    metadata = AgentMetadataDTO(
        name="contract",
        description="Contract analysis specialist.",
        capabilities=(
            "contract_review",
            "contract_analysis",
            "clause_extraction",
            "risk_analysis",
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
            prompt_builder=ContractPromptBuilder(),
            inference_policy=inference_policy,
        )
