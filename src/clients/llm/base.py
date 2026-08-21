"""
Base LLM client.

Defines the interface implemented by all LLM providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMStreamChunkDTO
from src.core.exceptions.client import ClientProviderError
from src.core.logger import get_logger

log = get_logger(__name__)

T = TypeVar(
    "T",
    bound=BaseModel,
)


class LLMClient(ABC):
    """
    Base class for all LLM providers.

    Implementations must be stateless and safe for concurrent use.
    """

    @property
    @abstractmethod
    def provider(
        self,
    ) -> str:
        """
        Return the provider name.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def model(
        self,
    ) -> str:
        """
        Return the configured model name.
        """
        raise NotImplementedError

    @abstractmethod
    async def generate(
        self,
        *,
        request: LLMRequestDTO,
    ) -> LLMResponseDTO:
        """
        Generate a text completion.
        """
        raise NotImplementedError

    async def generate_structured(
        self,
        *,
        request: LLMRequestDTO,
        response_model: type[T],
    ) -> T:
        """
        Generate and validate a structured response.
        """

        log.debug(
            "Generating structured response using provider '%s', "
            "model '%s', response_model='%s'.",
            self.provider,
            self.model,
            response_model.__name__,
        )

        structured_request = replace(
            request,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema(),
                },
            },
        )

        response = await self.generate(
            request=structured_request,
        )

        try:
            result = response_model.model_validate_json(
                response.content,
            )

        except ValidationError as exc:
            log.exception(
                "Failed to validate structured response using '%s'. " "Provider='%s', model='%s'.",
                response_model.__name__,
                self.provider,
                self.model,
            )

            raise ClientProviderError(
                message="LLM returned an invalid structured response.",
            ) from exc

        log.debug(
            "Successfully validated structured response using '%s'.",
            response_model.__name__,
        )

        return result

    @abstractmethod
    async def stream(
        self,
        *,
        request: LLMRequestDTO,
    ) -> AsyncIterator[LLMStreamChunkDTO]:
        """
        Stream a completion.
        """
        raise NotImplementedError
