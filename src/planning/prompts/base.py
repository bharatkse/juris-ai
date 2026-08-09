"""
Base planning prompt builder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Final, Generic, TypeVar

from src.core.exceptions.infrastructure import ConfigurationError
from src.core.models import GenerateRequest

RequestT = TypeVar("RequestT")


class BasePromptBuilder(
    ABC,
    Generic[RequestT],
):
    """
    Base class for planning prompt builders.

    A prompt builder transforms a request into a language
    model generation request.
    """

    _TEMPLATE_DIRECTORY: Final[Path] = Path(__file__).parent / "templates"

    @abstractmethod
    def build(
        self,
        *,
        request: RequestT,
    ) -> GenerateRequest:
        """
        Build a language model generation request.
        """

    @classmethod
    def load_template(
        cls,
        name: str,
    ) -> str:
        """
        Load a prompt template.
        """

        template = cls._TEMPLATE_DIRECTORY / name

        try:
            return template.read_text(
                encoding="utf-8",
            ).strip()

        except FileNotFoundError as exc:
            raise ConfigurationError(
                message=f"Prompt template '{name}' was not found.",
            ) from exc
