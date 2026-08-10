"""
Base prompt builder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.core.dto.agent import AgentRequestDTO
from src.core.dto.clients.llm import LLMRequestDTO
from src.core.dto.tool import RetrievedContentDTO


class BasePromptBuilder(ABC):
    """
    Base class for agent prompt builders.

    Prompt builders translate an agent-level request and retrieved
    context into a provider-independent LLM request.
    """

    template_name: str

    @abstractmethod
    def build(
        self,
        *,
        request: AgentRequestDTO,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ],
    ) -> LLMRequestDTO:
        """
        Build a provider-independent LLM request.
        """

    def load_template(self) -> str:
        """
        Load the prompt template associated with the builder.
        """

        template_path = Path(__file__).parent / "templates" / self.template_name

        return template_path.read_text(
            encoding="utf-8",
        )

    @staticmethod
    def build_context(
        *,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ],
    ) -> str:
        """
        Format retrieved content for inclusion in the prompt.
        """

        return "\n\n".join(item.content for item in context if item.content.strip())
