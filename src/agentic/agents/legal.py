"""
Legal AI agent.
"""

from __future__ import annotations

from typing import final

from adapters.clients.llm.base import LLMClient
from agentic.agents.base import BaseAgent
from agentic.agents.prompts.legal import LegalPromptBuilder
from agentic.tools.retrieval import RetrieverTool
from core.dto.agent import AgentMetadataDTO


@final
class LegalAgent(BaseAgent):
    """
    General-purpose legal assistant.
    """

    metadata = AgentMetadataDTO(
        name="legal",
        description="General-purpose legal assistant.",
        capabilities=(
            "legal_research",
            "legal_qa",
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
            prompt_builder=LegalPromptBuilder(),
            retriever=retriever,
        )
