"""
Base LLM client.

Defines the interface implemented by all LLM providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.clients.models import LLMRequest, LLMResponse, LLMStreamChunk
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
        request: LLMRequest,
    ) -> LLMResponse:
        """
        Generate a text completion.
        """
        raise NotImplementedError

    async def generate_structured(
        self,
        *,
        request: LLMRequest,
        response_model: type[T],
    ) -> T:
        """
        Generate and validate a structured response.
        """

        log.debug(
            "Generating structured response using provider '%s', model '%s'.",
            self.provider,
            self.model,
        )

        response = await self.generate(
            request=request,
        )

        try:
            result = response_model.model_validate_json(
                response.content,
            )

            log.debug(
                "Successfully validated structured response using '%s'.",
                response_model.__name__,
            )

            return result

        except ValidationError as exc:
            log.exception(
                "Failed to validate structured response using '%s'.",
                response_model.__name__,
            )

            raise ClientProviderError(
                message="LLM returned an invalid structured response.",
            ) from exc

    @abstractmethod
    async def stream(
        self,
        *,
        request: LLMRequest,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        Stream a completion.
        """
        raise NotImplementedError
