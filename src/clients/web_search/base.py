"""
Base web search client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.dto.clients.web_search import WebSearchRequestDTO, WebSearchResponseDTO


class WebSearchClient(ABC):
    """
    Base class for all web search providers.
    """

    @abstractmethod
    async def search(
        self,
        *,
        request: WebSearchRequestDTO,
    ) -> WebSearchResponseDTO:
        """
        Search the web.

        Args:
            request:
                Search request.

        Returns:
            Search response.
        """
        raise NotImplementedError
