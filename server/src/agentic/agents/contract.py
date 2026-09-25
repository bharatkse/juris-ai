"""
Contract AI agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from adapters.clients.llm.base import LLMClient
from agentic.agents.base import BaseAgent
from agentic.agents.prompts.contract import ContractPromptBuilder
from core.dto.agent import AgentMetadataDTO
from core.dto.inference import InferencePolicy, LLMTask

if TYPE_CHECKING:
    from agentic.policy.tool_catalog import AgentToolCatalog


@final
class ContractAgent(BaseAgent):
    """
    Contract analysis specialist.
    """

    metadata = AgentMetadataDTO(
        name="contract",
        description=(
            "Contract analysis specialist. Use for contract review and analysis, "
            "clause extraction, contract comparison and risk analysis."
        ),
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
        tool_catalog: AgentToolCatalog | None = None,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            prompt_builder=ContractPromptBuilder(),
            inference_policy=inference_policy,
            tool_catalog=tool_catalog,
        )
