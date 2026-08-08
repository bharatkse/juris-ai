"""
Contract AI agent.
"""

from __future__ import annotations

from typing import final

from src.agents.base import BaseAgent
from src.agents.prompts.contract import ContractPromptBuilder
from src.clients.llm.base import LLMClient
from src.core.models.agent import AgentMetadata
from src.tools.retrieval import RetrieverTool


@final
class ContractAgent(BaseAgent):
    """
    Contract analysis specialist.
    """

    metadata = AgentMetadata(
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

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        retriever: RetrieverTool,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            prompt_builder=ContractPromptBuilder(),
            retriever=retriever,
        )
