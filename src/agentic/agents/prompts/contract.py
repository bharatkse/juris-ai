"""
Contract prompt builder.
"""

from __future__ import annotations

from agentic.agents.prompts.base import BasePromptBuilder
from agentic.agents.prompts.token_budget import DEFAULT_RESERVED_OUTPUT_TOKENS
from core.dto.agent import AgentRequestDTO
from core.dto.clients.llm import LLMRequestDTO
from core.dto.tool import RetrievedContentDTO


class ContractPromptBuilder(BasePromptBuilder):
    """
    Prompt builder for the Contract agent.
    """

    template_name = "contract.md"

    def __init__(self) -> None:
        self._system_prompt = self.load_template()

    def build(
        self,
        *,
        request: AgentRequestDTO,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ],
        model: str,
        reserved_output_tokens: int = DEFAULT_RESERVED_OUTPUT_TOKENS,
    ) -> LLMRequestDTO:
        """
        Build a provider-independent LLM request.
        """

        messages = self.build_messages(
            system_prompt=self._system_prompt,
            request=request,
            context=context,
            model=model,
            reserved_output_tokens=reserved_output_tokens,
        )

        return LLMRequestDTO(
            messages=messages,
        )
