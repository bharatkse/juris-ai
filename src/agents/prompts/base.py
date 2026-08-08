"""
Base prompt builder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Final

from src.core.exceptions.infrastructure import ConfigurationError
from src.core.models import GenerateRequest
from src.core.models.agent import AgentRequest
from src.core.models.tool import RetrievedContent


class BasePromptBuilder(ABC):
    """
    Base class for agent prompt builders.

    A prompt builder transforms an agent request together with
    retrieved context into a language model generation request.
    """

    _TEMPLATE_DIRECTORY: Final[Path] = Path(__file__).parent / "templates"

    template_name: ClassVar[str]

    @abstractmethod
    def build(
        self,
        *,
        request: AgentRequest,
        context: tuple[
            RetrievedContent,
            ...,
        ],
    ) -> GenerateRequest:
        """
        Build a language model generation request.
        """

    @classmethod
    def load_template(
        cls,
    ) -> str:
        """
        Load the configured prompt template.

        Raises:
            ConfigurationError:
                If the prompt template does not exist.
        """

        template = cls._TEMPLATE_DIRECTORY / cls.template_name

        try:
            return template.read_text(
                encoding="utf-8",
            ).strip()

        except FileNotFoundError as exc:
            raise ConfigurationError(
                message=(f"Prompt template '{cls.template_name}' " "was not found."),
            ) from exc

    @staticmethod
    def build_context(
        *,
        context: tuple[
            RetrievedContent,
            ...,
        ],
    ) -> str:
        """
        Build retrieved context.
        """

        return "\n\n".join(item.content for item in context)
