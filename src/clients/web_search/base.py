"""
Base web search client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.clients.web_search.models import WebSearchRequest, WebSearchResponse


class WebSearchClient(ABC):
    """
    Base class for all web search providers.
    """

    @abstractmethod
    async def search(
        self,
        *,
        request: WebSearchRequest,
    ) -> WebSearchResponse:
        """
        Search the web.

        Args:
            request:
                Search request.

        Returns:
            Search response.
        """
        raise NotImplementedError
