"""
LLM client resolver.

Resolves the configured LLM client for request execution.

The resolver maintains the application's configured LLM providers and
returns the appropriate client. Each request is executed by exactly one
LLM client.
"""

from __future__ import annotations

from src.clients.llm.base import LLMClient
from src.core.enums import LLMProviderEnum
from src.core.exceptions.client import ClientConfigurationError
from src.core.logger import get_logger

log = get_logger(__name__)


class LLMResolver:
    """
    Resolve configured LLM clients.
    """

    def __init__(
        self,
        *,
        clients: dict[LLMProviderEnum, LLMClient],
        default_provider: LLMProviderEnum,
    ) -> None:
        self._clients = clients
        self._default_provider = default_provider

        log.info(
            "Initialized LLM resolver with %d provider(s). Default provider: '%s'.",
            len(clients),
            default_provider.value,
        )

    def get(
        self,
        provider: LLMProviderEnum | None = None,
    ) -> LLMClient:
        """
        Resolve an LLM client.

        Args:
            provider:
                Provider to resolve. If omitted, the default provider
                is returned.

        Returns:
            Configured LLM client.

        Raises:
            ClientConfigurationError:
                If the provider is not configured.
        """

        provider = provider or self._default_provider

        log.debug(
            "Resolving LLM provider '%s'.",
            provider.value,
        )

        try:
            client = self._clients[provider]

            log.debug(
                "Resolved LLM provider '%s'.",
                provider.value,
            )

            return client

        except KeyError as exc:
            log.exception(
                "LLM provider '%s' is not configured.",
                provider.value,
            )

            raise ClientConfigurationError(
                message=(f"LLM provider '{provider.value}' " "is not configured."),
            ) from exc

    def supports(
        self,
        provider: LLMProviderEnum,
    ) -> bool:
        """
        Return whether a provider is configured.
        """

        supported = provider in self._clients

        log.debug(
            "LLM provider '%s' supported: %s.",
            provider.value,
            supported,
        )

        return supported

    @property
    def default_provider(
        self,
    ) -> LLMProviderEnum:
        """
        Return the default provider.
        """

        return self._default_provider
